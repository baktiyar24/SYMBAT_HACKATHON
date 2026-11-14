import re
from datetime import timedelta
from sqlalchemy import select
from models import Product, AdCampaign, AdClick, Order
from database import utcnow
from crud import campaign_eligible, get, inventory_for, product_view
from services.metrics import ATTRIBUTION_DAYS

SYNONYMS = {
    'shampoo': 'шампунь', 'шампуни': 'шампунь', 'шампуня': 'шампунь',
    'санскрин': 'солнцезащитный крем', 'spf': 'солнцезащитный',
    'зубы': 'зубная паста', 'toothpaste': 'зубная паста',
    'витамин c': 'витамин с', 'vitamin c': 'витамин с', 'витамины': 'витамин',
}


def normalize(text):
    text = re.sub(r'\s+', ' ', str(text).casefold().replace('ё', 'е')).strip()
    for source, target in sorted(SYNONYMS.items(), key=lambda pair: -len(pair[0])):
        text = re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)', target, text)
    return text


def relevance(product, query):
    q = normalize(query)
    if not q:
        return 0.7  # explicitly generic category browsing, not inferred medical intent
    name, category = normalize(product.name), normalize(product.category)
    words = [normalize(w) for w in product.keywords]
    if q in name:
        return 1.0
    if q in words:
        return 0.95
    if q in category:
        return 0.85
    if any(q in w or w in q for w in words):
        return 0.8
    tokens = [t for t in q.split() if len(t) > 2]
    haystack = ' '.join([name, category, *words])
    return 0.7 if tokens and all(t in haystack for t in tokens) else 0.0


def smart_score(relevance_score, discount_score, performance_score, smart=True):
    if any(not 0 <= value <= 1 for value in [relevance_score, discount_score, performance_score]):
        raise ValueError('Оценки должны находиться в диапазоне 0–1')
    return 0.5*relevance_score + (0.2*discount_score if smart else 0) + 0.3*performance_score


def performance(session, campaign_id, now):
    # Use matured cohorts only; the newest 7 days still have an open attribution window.
    rows = session.execute(select(AdClick, Order).outerjoin(Order, Order.click_id == AdClick.id)
                           .where(AdClick.campaign_id == campaign_id,
                                  AdClick.created_at >= now-timedelta(days=37),
                                  AdClick.created_at < now-timedelta(days=ATTRIBUTION_DAYS))).all()
    count = len(rows)
    if count < 20:
        return 0.5, True, count
    confirmed = sum(1 for c, o in rows if o and o.status == 'confirmed' and o.confirmed_at
                    and c.created_at <= o.created_at <= o.confirmed_at <= c.created_at+timedelta(days=ATTRIBUTION_DAYS))
    return min((confirmed/count)/0.1, 1.0), False, count


def recommend_ads(session, query='', campaign_id=None, pharmacy_id=None, smart=True):
    query_db = select(AdCampaign).where(AdCampaign.status == 'active')
    if campaign_id:
        get(session, AdCampaign, campaign_id)
        query_db = query_db.where(AdCampaign.id == campaign_id)
    if pharmacy_id:
        query_db = query_db.where(AdCampaign.pharmacy_id == pharmacy_id)
    now, result = utcnow(), []
    for c in session.scalars(query_db):
        if not campaign_eligible(session, c):
            continue
        p = get(session, Product, c.product_id)
        rel = relevance(p, query)
        if rel == 0:
            continue
        view = product_view(session, p, inventory_for(session, p.id, c.pharmacy_id), now)
        perf, neutral, clicks = performance(session, c.id, now)
        discount = view['effective_discount']/100
        score = smart_score(rel, discount, perf, smart)
        reason = f'Соответствие запросу: {rel:.0%}; товар в наличии; актуальная скидка {view["effective_discount"]}%. '
        reason += 'Недостаточно зрелой статистики: нейтральная оценка 0,5.' if neutral else f'Историческая оценка по {clicks} кликам; не гарантия будущей эффективности.'
        result.append(dict(**view, campaign_id=c.id, relevance_score=rel, discount_score=discount,
                           performance_score=perf, smart_score=score, reason=reason,
                           performance_is_neutral=neutral, historical_clicks=clicks,
                           relevance=rel, performance=perf, score=score, explanation=reason))
    return sorted(result, key=lambda ad: (-ad['smart_score'], ad['campaign_id']))
