from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select, func
from models import AdCampaign, AdClick, AdImpression, Inventory, Product, Pharmacy
from database import utcnow
from services.ranking import smart_score
from conftest import event_chain


def test_ads_relevant_available(client):
    ads = client.get('/api/ads/recommendations?q=шампунь').json()['data']
    assert len(ads) >= 2
    assert all('Шампунь' in a['name'] and a['in_stock'] for a in ads)
    assert 'p3' not in [a['product_id'] for a in ads]
    assert client.get('/api/ads/recommendations?q=ноутбук').json()['data'] == []
    assert client.get('/api/ads/recommendations?campaign_id=c16').json()['data'] == []


def test_smart_score_and_discount_changes(client):
    assert smart_score(.9,.7,.8) == pytest.approx(.83)
    with pytest.raises(ValueError):
        smart_score(1.5,.1,.5)
    before = client.get('/api/ads/recommendations?q=шампунь&campaign_id=c2').json()['data'][0]
    assert client.patch('/api/discounts/d2',json={'discount_percent':35,'active':True}).status_code == 200
    after = client.get('/api/ads/recommendations?q=шампунь&campaign_id=c2').json()['data'][0]
    assert after['smart_score']-before['smart_score'] == pytest.approx(.07)
    assert after['smart_score'] == pytest.approx(.5*after['relevance_score']+.2*after['discount_score']+.3*after['performance_score'])


def test_neutral_performance(client,factory):
    with factory() as db:
        db.add(AdCampaign(id='new-c',product_id='p1',pharmacy_id='ph1',name='New',budget=100000,spent=0,cpc=100,status='active'))
        db.commit()
    ad = client.get('/api/ads/recommendations?campaign_id=new-c&q=шампунь').json()['data'][0]
    assert ad['performance_is_neutral'] and ad['performance_score']==.5 and ad['historical_clicks']==0


def test_impression_idempotency_and_conflict(client):
    payload={'impression_id':'unique-i','campaign_id':'c1','product_id':'p1','query':'Шампунь'}
    a=client.post('/api/ads/impression',json=payload)
    b=client.post('/api/ads/impression',json=payload)
    assert a.status_code==200 and a.json()==b.json()
    assert client.post('/api/ads/impression',json={**payload,'query':'шамп'}).status_code==409
    assert client.post('/api/ads/impression',json={**payload,'impression_id':'wrong','product_id':'p2'}).status_code==422
    assert client.post('/api/ads/impression',json={**payload,'impression_id':'irrelevant','query':'ноутбук'}).status_code==422
    assert client.post('/api/ads/impression',json={**payload,'impression_id':'stock','campaign_id':'c3','product_id':'p3'}).status_code==409


def test_click_unique_server_price(client,factory):
    imp, click=event_chain(client)
    with factory() as db:
        before=db.get(AdCampaign,'c1').spent
    payload={'click_id':click['click_id'],'impression_id':imp['impression_id'],'is_demo':True}
    assert client.post('/api/ads/click',json=payload).json()['data']==click
    assert client.post('/api/ads/click',json={**payload,'click_id':'second'}).status_code==409
    assert client.post('/api/ads/click',json={**payload,'cpc':0}).status_code==422
    with factory() as db:
        assert db.get(AdCampaign,'c1').spent==before
    assert client.post('/api/ads/click',json={'click_id':'unknown','impression_id':'absent'}).status_code==404


def test_budget_limit(client,factory):
    payload={'impression_id':'budget-i','campaign_id':'c1','product_id':'p1','query':'Шампунь'}
    assert client.post('/api/ads/impression',json=payload).status_code==200
    with factory() as db:
        c=db.get(AdCampaign,'c1'); c.budget=c.spent+c.cpc-1; db.commit()
    assert client.get('/api/ads/recommendations?campaign_id=c1&q=шампунь').json()['data']==[]
    assert client.post('/api/ads/click',json={'click_id':'budget-c','impression_id':'budget-i'}).status_code==409


def test_demo_order_price_stock_and_idempotency(client,factory):
    _,click=event_chain(client)
    client.patch('/api/discounts/d1',json={'discount_percent':25})
    before=client.get('/api/analytics/overview').json()['data']
    stock=next(i['stock_quantity'] for i in client.get('/api/inventory').json()['data'] if i['id']=='inv1')
    payload={'order_id':'order-1','click_id':click['click_id'],'product_id':'p1','quantity':2,'is_demo':True}
    a=client.post('/api/orders/demo',json=payload)
    assert a.status_code==200, a.text
    order=a.json()['data']
    assert order['total_price']==7200 and order['status']=='confirmed' and order['is_demo']
    assert client.post('/api/orders/demo',json=payload).json()==a.json()
    assert client.post('/api/orders/demo',json={**payload,'order_id':'other'}).status_code==409
    assert client.post('/api/orders/demo',json={**payload,'quantity':3}).status_code==409
    after=client.get('/api/analytics/overview').json()['data']
    assert after['confirmed_purchases']==before['confirmed_purchases']+1
    assert after['revenue']==before['revenue']+7200
    with factory() as db:
        assert db.get(Inventory,'inv1').stock_quantity==stock-2
    client.patch('/api/discounts/d1',json={'discount_percent':10})
    assert client.get('/api/analytics/overview').json()['data']['revenue']==after['revenue']


def test_pending_confirmation_cancel_once(client,factory):
    _,click=event_chain(client)
    base=client.get('/api/analytics/overview').json()['data']['confirmed_purchases']
    with factory() as db:
        stock=db.get(Inventory,'inv1').stock_quantity
    payload={'order_id':'pending','click_id':click['click_id'],'product_id':'p1','confirm':False}
    assert client.post('/api/orders/demo',json=payload).json()['data']['status']=='pending'
    assert client.get('/api/analytics/overview').json()['data']['confirmed_purchases']==base
    for _ in range(2):
        assert client.patch('/api/orders/demo/pending',json={'status':'confirmed'}).status_code==200
    assert client.get('/api/analytics/overview').json()['data']['confirmed_purchases']==base+1
    for _ in range(2):
        assert client.patch('/api/orders/demo/pending',json={'status':'cancelled'}).status_code==200
    assert client.get('/api/analytics/overview').json()['data']['confirmed_purchases']==base
    with factory() as db:
        assert db.get(Inventory,'inv1').stock_quantity==stock
    assert client.patch('/api/orders/demo/pending',json={'status':'confirmed'}).status_code==409


@pytest.mark.parametrize('quantity', [0,-1,1.5,True,'2',101])
def test_order_quantity(client,quantity):
    assert client.post('/api/orders/demo',json={'order_id':'bad','product_id':'p1','quantity':quantity}).status_code==422


def test_no_stock_and_expired_click(client,factory):
    _,click=event_chain(client)
    client.patch('/api/inventory/inv1',json={'stock_quantity':0})
    payload={'order_id':'nostock','product_id':'p1','click_id':click['click_id']}
    assert client.post('/api/orders/demo',json=payload).status_code==409
    client.patch('/api/inventory/inv1',json={'stock_quantity':5})
    with factory() as db:
        c=db.get(AdClick,click['click_id']); c.created_at=utcnow()-timedelta(days=8); db.commit()
    assert client.post('/api/orders/demo',json=payload).status_code==410


def test_concurrent_duplicate_click(client,factory):
    client.post('/api/ads/impression',json={'impression_id':'race-i','campaign_id':'c1','product_id':'p1','query':'Шампунь'})
    with factory() as db:
        c=db.get(AdCampaign,'c1'); before,cpc=c.spent,c.cpc
    payload={'click_id':'race-k','impression_id':'race-i'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _: client.post('/api/ads/click',json=payload),range(4)))
    assert all(r.status_code==200 for r in responses)
    with factory() as db:
        assert db.get(AdCampaign,'c1').spent==before+cpc


def test_concurrent_stock_last_unit(client,factory):
    _,a=event_chain(client,'a'); _,b=event_chain(client,'b')
    client.patch('/api/inventory/inv1',json={'stock_quantity':1})
    payloads=[{'order_id':f'last-{i}','product_id':'p1','click_id':c['click_id']} for i,c in enumerate([a,b])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda payload: client.post('/api/orders/demo',json=payload),payloads))
    assert sorted(r.status_code for r in responses)==[200,409]
    with factory() as db:
        assert db.get(Inventory,'inv1').stock_quantity==0


def test_demo_disabled(client,monkeypatch):
    monkeypatch.setenv('DEMO_ENABLED','false')
    assert client.patch('/api/inventory/inv1',json={'stock_quantity':1}).status_code==403
    assert client.post('/api/orders/demo',json={'order_id':'x','product_id':'p1'}).status_code==403
