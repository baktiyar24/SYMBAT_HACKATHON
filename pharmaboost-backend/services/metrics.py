"""Cohort analytics, calculated exclusively from persisted unique events."""
from datetime import date, datetime, time, timedelta
from sqlalchemy import select
from models import AdCampaign, AdImpression, AdClick, Order, Inventory, Product, Pharmacy, Discount
from database import utcnow
from crud import fail, get, discount_valid, money

ATTRIBUTION_DAYS = 7
RELEVANCE_THRESHOLD = 0.7


def calculate_metrics(impressions, clicks, purchases, spend, revenue, relevant, available, problematic):
    counts = [impressions, clicks, purchases, relevant, available, problematic]
    if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in counts) or min(spend, revenue) < 0:
        raise ValueError('Счётчики должны быть неотрицательными целыми')
    if purchases > clicks or clicks > impressions or max(relevant, available, problematic) > impressions:
        raise ValueError('Нарушена согласованность рекламной воронки')
    cvr = purchases / clicks if clicks else 0
    rr = relevant / impressions if impressions else 0
    ar = available / impressions if impressions else 0
    return dict(ctr=100*clicks/impressions if impressions else None,
                cpc=spend/clicks if clicks else None, cvr=100*cvr if clicks else None,
                cpa=spend/purchases if purchases else None, roas=revenue/spend if spend else None,
                rr=rr, ar=ar, rpi=100*cvr*rr*ar,
                wai=100*problematic/impressions if impressions else None)


def resolve_period(date_from=None, date_to=None, scenario='after'):
    if (date_from is None) != (date_to is None):
        fail(422, 'date_from и date_to передаются вместе', 'INVALID_PERIOD')
    if date_from is None:
        date_to = utcnow().date()
        date_from = date_to - timedelta(days=6)
        if scenario == 'before':
            date_from -= timedelta(days=7)
            date_to -= timedelta(days=7)
    if date_to < date_from or (date_to-date_from).days > 365:
        fail(422, 'Период должен быть от 1 до 366 дней', 'INVALID_PERIOD')
    return datetime.combine(date_from, time.min), datetime.combine(date_to+timedelta(days=1), time.min)


def previous_period(start, end):
    return start-(end-start), start


def empty_counts():
    return dict(impressions=0, clicks=0, confirmed_purchases=0, cancelled_orders=0,
                relevant_impressions=0, available_impressions=0, problematic_impressions=0,
                spend=0, revenue=0)


def overview(session, start, end, campaign_id=None, scenario='after'):
    campaign_query = select(AdCampaign)
    if campaign_id:
        get(session, AdCampaign, campaign_id)
        campaign_query = campaign_query.where(AdCampaign.id == campaign_id)
    campaigns = list(session.scalars(campaign_query))
    ids = [c.id for c in campaigns]
    as_of = min(end, utcnow())
    # Group ALL outcomes by their impression's date (cohort). Thus daily totals,
    # campaign totals and overview are additive and purchases <= clicks <= views.
    query = (select(AdImpression, AdClick, Order)
             .outerjoin(AdClick, AdClick.impression_id == AdImpression.id)
             .outerjoin(Order, Order.click_id == AdClick.id)
             .where(AdImpression.campaign_id.in_(ids), AdImpression.created_at >= start,
                    AdImpression.created_at < as_of).order_by(AdImpression.created_at))
    totals = empty_counts()
    daily = {}
    day = start.date()
    while day < end.date():
        daily[day.isoformat()] = dict(date=day.isoformat(), **empty_counts())
        day += timedelta(days=1)
    reasons = dict(low_relevance=0, unavailable_product=0, invalid_advertised_discount=0)
    for imp, click, order in session.execute(query):
        row = daily[imp.created_at.date().isoformat()]
        low = imp.relevance_score < RELEVANCE_THRESHOLD
        unavailable = not imp.product_available
        invalid = imp.discount_advertised and not imp.valid_discount
        row['impressions'] += 1
        row['relevant_impressions'] += int(not low)
        row['available_impressions'] += int(not unavailable)
        row['problematic_impressions'] += int(low or unavailable or invalid)
        reasons['low_relevance'] += int(low)
        reasons['unavailable_product'] += int(unavailable)
        reasons['invalid_advertised_discount'] += int(invalid)
        if click and imp.created_at <= click.created_at < as_of:
            row['clicks'] += 1
            row['spend'] += click.charged_cpc
            if order and order.created_at < as_of and click.created_at <= order.created_at <= click.created_at+timedelta(days=ATTRIBUTION_DAYS):
                if order.status == 'confirmed' and order.confirmed_at and click.created_at <= order.confirmed_at < as_of and order.confirmed_at <= click.created_at+timedelta(days=ATTRIBUTION_DAYS):
                    row['confirmed_purchases'] += 1
                    row['revenue'] += order.total_price
                elif order.status == 'cancelled':
                    row['cancelled_orders'] += 1
    for row in daily.values():
        for key in totals:
            totals[key] += row[key]
        row['spend'], row['revenue'] = money(row['spend']), money(row['revenue'])
    totals['spend'], totals['revenue'] = money(totals['spend']), money(totals['revenue'])
    coefficients = calculate_metrics(totals['impressions'], totals['clicks'], totals['confirmed_purchases'],
                                     totals['spend'], totals['revenue'], totals['relevant_impressions'],
                                     totals['available_impressions'], totals['problematic_impressions'])
    offers = {(c.product_id, c.pharmacy_id) for c in campaigns}
    stock = list(session.execute(select(Inventory, Product, Pharmacy)
                                .join(Product, Product.id == Inventory.product_id)
                                .join(Pharmacy, Pharmacy.id == Inventory.pharmacy_id)))
    available = sum(1 for inv, p, ph in stock if (p.id, ph.id) in offers and inv.stock_quantity > 0 and p.active and ph.active)
    discounts = list(session.scalars(select(Discount)))
    return dict(**totals, **coefficients, attributed_revenue=totals['revenue'], budget=money(sum(c.budget for c in campaigns)),
                lifetime_spent=money(sum(c.spent for c in campaigns)), active_campaigns=sum(c.status == 'active' for c in campaigns),
                available_products=available, active_discounts=sum(discount_valid(d) and (d.product_id, d.pharmacy_id) in offers for d in discounts),
                daily=list(daily.values()), period_start=start.date().isoformat(), period_end=(end-timedelta(days=1)).date().isoformat(),
                scenario=scenario, is_demo=True, attribution_days=ATTRIBUTION_DAYS, problem_reasons=reasons)


def campaign_analytics(session, start, end, campaign_id=None, scenario='after'):
    query = select(AdCampaign).order_by(AdCampaign.id)
    if campaign_id:
        get(session, AdCampaign, campaign_id)
        query = query.where(AdCampaign.id == campaign_id)
    return [dict(**overview(session, start, end, c.id, scenario), campaign_id=c.id, product_id=c.product_id,
                 pharmacy_id=c.pharmacy_id, name=c.name, status=c.status) for c in session.scalars(query)]


def relative_change(current, previous):
    return (current/previous-1)*100 if current is not None and previous not in (None, 0) else None


def rpi_analytics(session, start, end, campaign_id=None):
    current = overview(session, start, end, campaign_id)
    baseline = overview(session, *previous_period(start, end), campaign_id, 'before')
    return dict(rpi=current['rpi'], cvr=(current['cvr'] or 0)/100,
                relevance_rate=current['rr'], availability_rate=current['ar'], previous_rpi=baseline['rpi'],
                change_percent=relative_change(current['rpi'], baseline['rpi']), current=current, baseline=baseline,
                experimental=True, note='RPI — экспериментальная составная метрика, не доказательство дополнительных продаж.')


def wai_analytics(session, start, end, campaign_id=None):
    current = overview(session, start, end, campaign_id)
    baseline = overview(session, *previous_period(start, end), campaign_id, 'before')
    value, previous = current['wai'], baseline['wai']
    return dict(wai=value, problematic_impressions=current['problematic_impressions'], total_impressions=current['impressions'],
                reasons=current['problem_reasons'], previous_wai=previous, change_percent=relative_change(value, previous),
                change_percentage_points=value-previous if value is not None and previous is not None else None,
                period_start=current['period_start'], period_end=current['period_end'],
                previous_period_start=baseline['period_start'], previous_period_end=baseline['period_end'],
                note='Причины могут пересекаться; проблемный показ учитывается один раз. WAI не измеряет денежную потерю.')
