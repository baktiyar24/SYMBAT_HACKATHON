from sqlalchemy import select
from database import utcnow
from models import AdCampaign, Product
from crud import discount_for, discount_valid, inventory_for, get
from services.metrics import overview


def recommendations(session, start, end, campaign_id=None):
    query = select(AdCampaign).order_by(AdCampaign.id)
    if campaign_id:
        get(session, AdCampaign, campaign_id)
        query = query.where(AdCampaign.id == campaign_id)
    output = []
    for c in session.scalars(query):
        a = overview(session, start, end, c.id)
        p = get(session, Product, c.product_id)
        inv = inventory_for(session, p.id, c.pharmacy_id)
        discount = discount_for(session, p.id, c.pharmacy_id)

        def add(kind, priority, title, description, action, status='Рекомендуется'):
            output.append(dict(id=f'{c.id}-{kind}', campaign_id=c.id, product_id=p.id, type=kind,
                               priority=priority, title=title, description=description, action=action,
                               status=status, text=f'{p.name}: {description} {action}'))

        if a['impressions'] >= 30 and a['rr'] < .8:
            add('low_relevance', 'high', 'Низкая релевантность рекламы',
                f'Доля релевантных показов {a["rr"]:.1%}.', 'Пересмотреть ключевые слова и категории.', 'Требует внимания')
        if a['clicks'] >= 20 and (a['cvr'] or 0) < 3 and (a['cpc'] or 0) > 50:
            add('high_cpc_low_conversion', 'high', 'Клики дороги относительно конверсии',
                f'CPC {a["cpc"]:.2f} ₸; CVR {(a["cvr"] or 0):.2f}%.',
                'Проверить цену, карточку и настройки кампании; сравнить с контрольной группой.', 'Требует внимания')
        if inv.stock_quantity == 0:
            add('out_of_stock', 'high', 'Товар закончился', 'В выбранной аптеке остаток равен нулю.',
                'Пополнить остаток. Товар уже исключён из новых рекламных рекомендаций.', 'Требует внимания')
        if discount and discount.active and discount.end_date <= utcnow():
            add('expired_discount', 'medium', 'Акция истекла', 'Скидка больше не применяется к цене и ранжированию.',
                'Обновить даты акции или отключить устаревший рекламный материал.')
        if a['impressions'] >= 30 and (a['wai'] or 0) > 20:
            add('high_wai', 'high', 'Высокая доля проблемных показов', f'WAI {a["wai"]:.2f}%.',
                'Изучить причины качества; WAI не равен денежной потере.', 'Требует внимания')
        if a['clicks'] >= 20 and a['rr'] >= .8 and (a['cvr'] or 0) >= 3 and inv.stock_quantity > 0:
            add('strong_offer', 'low', 'Релевантное предложение с конверсией',
                f'RR {a["rr"]:.1%}, CVR {a["cvr"]:.2f}%.', 'Протестировать долю показов в пределах бюджета.', 'Оптимизировано')
        if inv.stock_quantity > 0 and discount_valid(discount) and discount.discount_percent >= 15:
            add('current_discount', 'medium', 'Актуальная скидка', f'Действует скидка {discount.discount_percent}%.',
                'Тестировать продвижение только для релевантных запросов.')
    order = {'high': 0, 'medium': 1, 'low': 2}
    return sorted(output, key=lambda r: (order[r['priority']], r['id']))
