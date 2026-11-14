"""Database operations. Mutation callers must hold get_write_db's transaction."""
import hashlib
import json
import os
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import as_utc, iso, utcnow
from models import Product, Pharmacy, Inventory, Discount, AdCampaign, AdImpression, AdClick, Order


def fail(status: int, message: str, code='BUSINESS_RULE'):
    raise HTTPException(status, detail={'code': code, 'message': message})


def demo_enabled() -> bool:
    return os.getenv('DEMO_ENABLED', 'true').lower() == 'true'


def require_demo():
    if not demo_enabled():
        fail(403, 'Демонстрационные изменения отключены', 'DEMO_DISABLED')


def get(session: Session, model, identifier):
    obj = session.get(model, identifier)
    if obj is None:
        fail(404, f'{model.__name__}: объект {identifier} не найден', 'NOT_FOUND')
    return obj


def money(tiyn: int) -> float:
    return tiyn / 100  # serialization only; business arithmetic stays integer


def fingerprint(body) -> str:
    return hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def existing_event(session, model, identifier, digest):
    existing = session.get(model, identifier)
    if existing and existing.request_fingerprint != digest:
        fail(409, 'Этот ID уже использован с другим содержимым', 'IDEMPOTENCY_CONFLICT')
    return existing


def inventory_for(session, product_id, pharmacy_id=None):
    query = select(Inventory).where(Inventory.product_id == product_id)
    if pharmacy_id:
        query = query.where(Inventory.pharmacy_id == pharmacy_id)
    items = list(session.scalars(query.order_by(Inventory.id)))
    if not items:
        fail(404, 'Предложение в аптеке не найдено', 'OFFER_NOT_FOUND')
    if not pharmacy_id and len(items) > 1:
        fail(422, 'Для товара с несколькими аптеками укажите pharmacy_id', 'AMBIGUOUS_PHARMACY')
    return items[0]


def discount_for(session, product_id, pharmacy_id):
    return session.scalar(select(Discount).where(Discount.product_id == product_id, Discount.pharmacy_id == pharmacy_id))


def discount_valid(discount, now=None):
    now = now or utcnow()
    return bool(discount and discount.active and discount.discount_percent > 0 and discount.start_date <= now < discount.end_date)


def discounted_price(price: int, percent: int) -> int:
    return (price * (100 - percent) + 50) // 100  # half-up to one tiyn


def price_for(session, product, pharmacy_id, now=None):
    discount = discount_for(session, product.id, pharmacy_id)
    percent = discount.discount_percent if discount_valid(discount, now) else 0
    return discounted_price(product.price, percent), percent, discount


def discount_view(session, d, now=None):
    product = get(session, Product, d.product_id)
    valid = discount_valid(d, now)
    return dict(id=d.id, product_id=d.product_id, pharmacy_id=d.pharmacy_id,
                discount_percent=d.discount_percent, percent=d.discount_percent,
                start_date=iso(d.start_date), end_date=iso(d.end_date), start_at=iso(d.start_date), end_at=iso(d.end_date),
                active=d.active, is_current=valid, price=money(product.price),
                new_price=money(discounted_price(product.price, d.discount_percent if valid else 0)))


def product_view(session, product, inventory, now=None):
    price, percent, discount = price_for(session, product, inventory.pharmacy_id, now)
    pharmacy = get(session, Pharmacy, inventory.pharmacy_id)
    return dict(id=product.id, product_id=product.id, pharmacy_id=pharmacy.id, inventory_id=inventory.id,
                name=product.name, category=product.category, description=product.description,
                image_url=product.image_url, price=money(product.price), current_price=money(price),
                active=product.active, ad_allowed=product.ad_allowed,
                in_stock=inventory.stock_quantity > 0 and pharmacy.active and product.active,
                stock_quantity=inventory.stock_quantity, discount=discount_view(session, discount, now) if discount else None,
                effective_discount=percent, brand=product.brand, keywords=product.keywords,
                volume=product.volume, shape=product.shape, color=product.color, pharmacy=pharmacy.name)


def inventory_view(inv):
    return dict(id=inv.id, product_id=inv.product_id, pharmacy_id=inv.pharmacy_id,
                stock_quantity=inv.stock_quantity, updated_at=iso(inv.updated_at))


def list_products(session, q='', category=None, pharmacy_id=None):
    from services.ranking import relevance
    query = select(Product, Inventory).join(Inventory, Inventory.product_id == Product.id).join(Pharmacy, Pharmacy.id == Inventory.pharmacy_id).where(Product.active.is_(True), Pharmacy.active.is_(True))
    if pharmacy_id:
        get(session, Pharmacy, pharmacy_id)
        query = query.where(Inventory.pharmacy_id == pharmacy_id)
    rows = [(p, inv) for p, inv in session.execute(query) if (not category or p.category == category) and (not q or relevance(p, q) > 0)]
    rows.sort(key=lambda pair: (-relevance(pair[0], q), pair[0].id, pair[1].pharmacy_id))
    now = utcnow()
    return [product_view(session, p, inv, now) for p, inv in rows]


def patch_discount(session, identifier, body):
    d = get(session, Discount, identifier)
    product = get(session, Product, d.product_id)
    pharmacy = get(session, Pharmacy, d.pharmacy_id)
    inventory = inventory_for(session, product.id, pharmacy.id)
    changes = body.model_dump(exclude_unset=True)
    start = as_utc(changes['start_date']) if 'start_date' in changes else d.start_date
    end = as_utc(changes['end_date']) if 'end_date' in changes else d.end_date
    if start >= end:
        fail(422, 'Дата окончания должна быть позже начала', 'INVALID_DATE_RANGE')
    active = changes.get('active', d.active)
    # Turning off an invalid offer must remain possible.
    if active and (not product.active or not pharmacy.active or inventory.stock_quantity <= 0):
        fail(409, 'Нельзя включить акцию для неактивного или отсутствующего товара', 'OFFER_UNAVAILABLE')
    d.start_date, d.end_date = start, end
    if 'discount_percent' in changes:
        d.discount_percent = changes['discount_percent']
    d.active = active
    session.flush()
    return discount_view(session, d)


def patch_inventory(session, identifier, quantity):
    inv = get(session, Inventory, identifier)
    if quantity > 0 and (not get(session, Product, inv.product_id).active or not get(session, Pharmacy, inv.pharmacy_id).active):
        fail(409, 'Товар или аптека неактивны')
    inv.stock_quantity, inv.updated_at = quantity, utcnow()
    session.flush()
    return inventory_view(inv)


def patch_product_compat(session, product_id, body):
    """Existing frontend uses a combined demo-edit operation. All edits are atomic."""
    from schemas import DiscountPatch
    if body.product_id and body.product_id != product_id:
        fail(422, 'product_id в URL и теле не совпадают')
    p = get(session, Product, product_id)
    inv = inventory_for(session, product_id, body.pharmacy_id)
    if body.in_stock is not None:
        # A boolean UI switch replenishes exactly 20 demo units if empty.
        patch_inventory(session, inv.id, max(inv.stock_quantity, 20) if body.in_stock else 0)
    if body.percent is not None or body.active is not None:
        d = discount_for(session, product_id, inv.pharmacy_id)
        if d is None:
            d = Discount(id=f'd-{product_id}-{inv.pharmacy_id}', product_id=product_id, pharmacy_id=inv.pharmacy_id,
                         discount_percent=0, active=False, start_date=utcnow(), end_date=utcnow()+timedelta(days=30))
            session.add(d)
            session.flush()
        changes = {}
        if body.percent is not None:
            changes['discount_percent'] = body.percent
        if body.active is not None:
            changes['active'] = body.active
        patch_discount(session, d.id, DiscountPatch(**changes))
    return product_view(session, p, inv)


def campaign_eligible(session, c):
    p, ph = get(session, Product, c.product_id), get(session, Pharmacy, c.pharmacy_id)
    inv = inventory_for(session, p.id, ph.id)
    return (c.status == 'active' and p.active and p.ad_allowed and ph.active and inv.stock_quantity > 0
            and c.spent < c.budget and c.spent + c.cpc <= c.budget)


def impression_view(i):
    return dict(impression_id=i.id, campaign_id=i.campaign_id, product_id=i.product_id, pharmacy_id=i.pharmacy_id,
                search_query=i.search_query, relevance_score=i.relevance_score, product_available=i.product_available,
                valid_discount=i.valid_discount, discount_advertised=i.discount_advertised,
                advertised_discount_percent=i.advertised_discount_percent, is_demo=i.is_demo, created_at=iso(i.created_at))


def record_impression(session, body):
    from services.ranking import relevance
    digest = fingerprint(body)
    old = existing_event(session, AdImpression, body.impression_id, digest)
    if old:
        return impression_view(old)
    c = get(session, AdCampaign, body.campaign_id)
    if c.product_id != body.product_id or (body.pharmacy_id and c.pharmacy_id != body.pharmacy_id):
        fail(422, 'Товар/аптека не соответствуют кампании', 'RELATION_MISMATCH')
    if not campaign_eligible(session, c):
        fail(409, 'Кампания недоступна: проверьте статус, товар, остаток и бюджет', 'CAMPAIGN_UNAVAILABLE')
    score = relevance(get(session, Product, c.product_id), body.search_query)
    if score == 0:
        fail(422, 'Объявление не соответствует запросу', 'IRRELEVANT_AD')
    d = discount_for(session, c.product_id, c.pharmacy_id)
    advertised = body.advertised_discount_percent > 0
    valid = not advertised or (discount_valid(d) and d.discount_percent == body.advertised_discount_percent)
    imp = AdImpression(id=body.impression_id, campaign_id=c.id, product_id=c.product_id, pharmacy_id=c.pharmacy_id,
                       search_query=body.search_query, relevance_score=score, product_available=True,
                       valid_discount=valid, discount_advertised=advertised,
                       advertised_discount_percent=body.advertised_discount_percent, is_demo=True,
                       request_fingerprint=digest, created_at=utcnow())
    session.add(imp)
    session.flush()
    return impression_view(imp)


def click_view(click):
    return dict(click_id=click.id, impression_id=click.impression_id, campaign_id=click.campaign_id,
                product_id=click.product_id, pharmacy_id=click.pharmacy_id,
                charged_cpc=money(click.charged_cpc), is_demo=True, created_at=iso(click.created_at))


def record_click(session, body):
    digest = fingerprint(body)
    old = existing_event(session, AdClick, body.click_id, digest)
    if old:
        return click_view(old)
    imp = get(session, AdImpression, body.impression_id)
    for key in ['campaign_id', 'product_id', 'pharmacy_id']:
        if getattr(body, key) and getattr(body, key) != getattr(imp, key):
            fail(422, 'Параметры клика не соответствуют показу', 'RELATION_MISMATCH')
    if session.scalar(select(AdClick.id).where(AdClick.impression_id == imp.id)):
        fail(409, 'У этого показа уже есть клик', 'IMPRESSION_ALREADY_CLICKED')
    c = get(session, AdCampaign, imp.campaign_id)
    if not campaign_eligible(session, c):
        fail(409, 'Невозможно списать CPC: кампания, бюджет или товар недоступны', 'CAMPAIGN_UNAVAILABLE')
    now = utcnow()
    if now - imp.created_at > timedelta(hours=24):
        fail(410, 'Срок регистрации клика истёк (24 часа)', 'IMPRESSION_EXPIRED')
    click = AdClick(id=body.click_id, impression_id=imp.id, campaign_id=c.id, product_id=c.product_id,
                    pharmacy_id=c.pharmacy_id, charged_cpc=c.cpc, request_fingerprint=digest, created_at=now)
    c.spent += c.cpc
    session.add(click)
    session.flush()
    return click_view(click)


def order_view(session, order):
    click = session.get(AdClick, order.click_id) if order.click_id else None
    return dict(order_id=order.id, click_id=order.click_id, campaign_id=click.campaign_id if click else None,
                product_id=order.product_id, pharmacy_id=order.pharmacy_id, quantity=order.quantity,
                total_price=money(order.total_price), amount=money(order.total_price), status=order.status,
                is_demo=order.is_demo, created_at=iso(order.created_at), confirmed_at=iso(order.confirmed_at) if order.confirmed_at else None)


def create_order(session, body):
    from services.metrics import ATTRIBUTION_DAYS
    digest = fingerprint(body)
    old = existing_event(session, Order, body.order_id, digest)
    if old:
        return order_view(session, old)
    p = get(session, Product, body.product_id)
    click = get(session, AdClick, body.click_id) if body.click_id else None
    now = utcnow()
    if click:
        if click.product_id != p.id or (body.pharmacy_id and body.pharmacy_id != click.pharmacy_id):
            fail(422, 'Товар или аптека не соответствуют клику', 'RELATION_MISMATCH')
        if session.scalar(select(Order.id).where(Order.click_id == click.id)):
            fail(409, 'У этого клика уже есть заказ', 'CLICK_ALREADY_ORDERED')
        if now - click.created_at > timedelta(days=ATTRIBUTION_DAYS):
            fail(410, 'Окно атрибуции покупки истекло', 'ATTRIBUTION_EXPIRED')
    inv = inventory_for(session, p.id, click.pharmacy_id if click else body.pharmacy_id)
    if not p.active or not get(session, Pharmacy, inv.pharmacy_id).active or inv.stock_quantity < body.quantity:
        fail(409, 'Недостаточно товара в выбранной аптеке', 'INSUFFICIENT_STOCK')
    unit_price, _, _ = price_for(session, p, inv.pharmacy_id, now)
    order = Order(id=body.order_id, click_id=click.id if click else None, product_id=p.id,
                  pharmacy_id=inv.pharmacy_id, quantity=body.quantity, total_price=unit_price*body.quantity,
                  status='confirmed' if body.confirm else 'pending', is_demo=True,
                  confirmed_at=now if body.confirm else None, created_at=now, request_fingerprint=digest)
    inv.stock_quantity -= body.quantity
    inv.updated_at = now
    session.add(order)
    session.flush()
    return order_view(session, order)


def change_order_status(session, identifier, status):
    from services.metrics import ATTRIBUTION_DAYS
    order = get(session, Order, identifier)
    if not order.is_demo:
        fail(403, 'Этот endpoint изменяет только тестовые заказы')
    if order.status == status:
        return order_view(session, order)
    if order.status == 'cancelled':
        fail(409, 'Отменённый заказ нельзя подтвердить')
    if status == 'confirmed':
        click = session.get(AdClick, order.click_id) if order.click_id else None
        if click and utcnow() - click.created_at > timedelta(days=ATTRIBUTION_DAYS):
            fail(410, 'Окно атрибуции истекло; отмените резерв')
        order.confirmed_at = utcnow()
    else:
        inv = inventory_for(session, order.product_id, order.pharmacy_id)
        inv.stock_quantity += order.quantity
        inv.updated_at = utcnow()
        order.confirmed_at = None
    order.status = status
    session.flush()
    return order_view(session, order)
