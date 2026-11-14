from datetime import timedelta
import pytest
from sqlalchemy import select, func
from models import AdCampaign, AdClick, AdImpression, Order
from database import utcnow
from services.metrics import calculate_metrics
from conftest import event_chain


def test_exact_standard_metrics():
    a=calculate_metrics(20000,1000,50,100000,300000,18000,19000,2500)
    assert a['ctr']==5 and a['cvr']==5 and a['cpc']==100
    assert a['cpa']==2000 and a['roas']==3
    assert a['rpi']==pytest.approx(4.275) and a['wai']==12.5


def test_zero_denominators():
    a=calculate_metrics(0,0,0,0,0,0,0,0)
    assert all(a[k] is None for k in ('ctr','cpc','cvr','cpa','roas','wai'))
    assert a['rpi']==0 and a['rr']==0 and a['ar']==0
    b=calculate_metrics(100,10,0,100,0,90,100,10)
    assert b['cpa'] is None and b['roas']==0 and b['rpi']==0
    with pytest.raises(ValueError):
        calculate_metrics(1,2,3,0,0,0,0,0)


def test_analytics_consistency(client,factory):
    total=client.get('/api/analytics/overview').json()['data']
    campaigns=client.get('/api/analytics/campaigns').json()['data']
    for key in ['impressions','clicks','confirmed_purchases','spend','revenue','problematic_impressions']:
        assert sum(c[key] for c in campaigns)==pytest.approx(total[key])
        assert sum(day[key] for day in total['daily'])==pytest.approx(total[key])
    assert total['confirmed_purchases'] <= total['clicks'] <= total['impressions']
    assert total['rpi']==pytest.approx(100*(total['confirmed_purchases']/total['clicks'])*total['rr']*total['ar'])
    with factory() as db:
        assert sum(db.scalars(select(AdCampaign.spent)))==db.scalar(select(func.sum(AdClick.charged_cpc)))


def test_wai_union_reasons_not_sum(client,factory):
    with factory() as db:
        db.add(AdCampaign(id='quality',product_id='p1',pharmacy_id='ph1',name='Quality',budget=10000,spent=0,cpc=100,status='active'))
        db.flush()
        for i, values in enumerate([(.2,False,False,True),(.95,True,True,False),(.95,True,False,False),(.95,True,False,True)]):
            relevance,available,valid,advertised=values
            db.add(AdImpression(id=f'quality-{i}',campaign_id='quality',product_id='p1',pharmacy_id='ph1',search_query='шампунь',
                                relevance_score=relevance,product_available=available,valid_discount=valid,discount_advertised=advertised,
                                advertised_discount_percent=10 if advertised else 0,created_at=utcnow(),request_fingerprint='test',is_demo=True))
        db.commit()
    data=client.get('/api/analytics/wai?campaign_id=quality').json()['data']
    assert data['total_impressions']==4 and data['problematic_impressions']==2 and data['wai']==50
    assert sum(data['reasons'].values())==4  # 3 reasons for first, 1 for fourth; each view counted once
    assert data['previous_wai'] is None


def test_stale_advertised_discount_recorded(client):
    base=client.get('/api/analytics/wai?campaign_id=c1').json()['data']
    payload={'impression_id':'stale','campaign_id':'c1','product_id':'p1','query':'шампунь','advertised_discount_percent':99}
    imp=client.post('/api/ads/impression',json=payload).json()['data']
    assert imp['discount_advertised'] and not imp['valid_discount']
    after=client.get('/api/analytics/wai?campaign_id=c1').json()['data']
    assert after['problematic_impressions']==base['problematic_impressions']+1


def test_previous_period_calculated(client):
    r=client.get('/api/analytics/rpi').json()['data']
    assert r['change_percent']==pytest.approx((r['rpi']/r['previous_rpi']-1)*100)
    assert r['cvr']==pytest.approx(r['current']['cvr']/100)
    assert r['current']['period_start']>r['baseline']['period_end']
    w=client.get('/api/analytics/wai').json()['data']
    assert w['change_percentage_points']==pytest.approx(w['wai']-w['previous_wai'])


def test_period_errors_and_empty(client):
    assert client.get('/api/analytics/overview?date_from=2026-01-01').status_code==422
    assert client.get('/api/analytics/overview?date_from=2026-02-01&date_to=2026-01-01').status_code==422
    empty=client.get('/api/analytics/overview?date_from=2000-01-01&date_to=2000-01-07').json()['data']
    assert empty['impressions']==0 and empty['cpa'] is None and empty['rpi']==0
    assert client.get('/api/analytics/overview?campaign_id=missing').status_code==404


def test_attribution_window_and_organic(client,factory):
    _,click=event_chain(client)
    with factory() as db:
        c=db.get(AdClick,click['click_id']); i=db.get(AdImpression,c.impression_id)
        c.created_at=utcnow()-timedelta(days=10)
        i.created_at=c.created_at-timedelta(seconds=1)
        db.add(Order(id='late-order',click_id=c.id,product_id='p1',pharmacy_id='ph1',quantity=1,total_price=500000,
                     status='confirmed',created_at=utcnow(),confirmed_at=utcnow(),is_demo=True,request_fingerprint='test'))
        db.commit()
    start=(utcnow()-timedelta(days=14)).date().isoformat(); end=utcnow().date().isoformat()
    before=client.get(f'/api/analytics/overview?date_from={start}&date_to={end}').json()['data']
    client.post('/api/orders/demo',json={'order_id':'organic','product_id':'p1','quantity':1})
    after=client.get(f'/api/analytics/overview?date_from={start}&date_to={end}').json()['data']
    assert after['revenue']==before['revenue']
    with factory() as db:
        late=db.get(Order,'late-order'); db.delete(late); db.commit()
    without=client.get(f'/api/analytics/overview?date_from={start}&date_to={end}').json()['data']
    assert without['revenue']==before['revenue']


def test_recommendations_derived(client):
    before=client.get('/api/recommendations?campaign_id=c1').json()['data']
    assert not any(r['type']=='out_of_stock' for r in before)
    client.patch('/api/inventory/inv1',json={'stock_quantity':0})
    after=client.get('/api/recommendations?campaign_id=c1').json()['data']
    assert any(r['type']=='out_of_stock' for r in after)
