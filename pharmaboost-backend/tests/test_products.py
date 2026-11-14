from datetime import timedelta
import pytest
from sqlalchemy import func, select
from database import utcnow, iso
from models import Product, Pharmacy, AdCampaign, AdImpression, AdClick, Order
from seed import seed_database
from crud import discounted_price


@pytest.mark.parametrize('query', ['шампунь', 'ШАМПУНЬ', 'шамп', 'shampoo'])
def test_search(client, query):
    data = client.get('/api/products/search', params={'q':query}).json()['data']
    assert len(data) >= 3
    assert all('Шампунь' in p['name'] for p in data)


def test_empty_and_category(client):
    assert client.get('/api/products/search', params={'q':'несуществующий'}).json()['data'] == []
    items = client.get('/api/products/search', params={'category':'Волосы'}).json()['data']
    assert items and all(p['category'] == 'Уход за волосами' for p in items)
    assert client.get('/api/products/search', params={'q':'витамин C'}).json()['data']


def test_seed_size_idempotency(factory):
    with factory() as db:
        counts = [db.scalar(select(func.count()).select_from(m)) for m in (Product, Pharmacy, AdCampaign, AdImpression, AdClick, Order)]
        assert counts[0] >= 20 and counts[1] >= 3 and counts[2] >= 10 and counts[3] > counts[4] > counts[5] > 0
        assert db.scalar(select(func.count(func.distinct(Product.category)))) >= 5
    assert seed_database(factory) is False
    with factory() as db:
        assert counts == [db.scalar(select(func.count()).select_from(m)) for m in (Product, Pharmacy, AdCampaign, AdImpression, AdClick, Order)]


@pytest.mark.parametrize('percent', [-1,101,12.5,'30',True,None])
def test_invalid_discount(client, percent):
    assert client.patch('/api/discounts/d1',json={'discount_percent':percent}).status_code == 422


@pytest.mark.parametrize('percent', [0,25,100])
def test_discount_price(client, percent):
    data = client.patch('/api/discounts/d1',json={'discount_percent':percent}).json()['data']
    assert data['new_price'] == 4800*(100-percent)/100
    assert discounted_price(101,50) == 51


def test_expired_future_and_dates(client):
    current = client.get('/api/discounts').json()['data']
    assert all(d['is_current'] for d in current)
    assert 'd7' not in [d['id'] for d in current] and 'd14' not in [d['id'] for d in current]
    all_items = client.get('/api/discounts?include_all=true').json()['data']
    assert len(all_items) == 20
    p = next(p for p in client.get('/api/products').json()['data'] if p['product_id']=='p7')
    assert p['current_price'] == p['price']
    assert client.patch('/api/discounts/d1',json={'end_date':iso(utcnow()-timedelta(days=40))}).status_code == 422
    assert client.patch('/api/discounts/d1',json={'start_date':'2026-01-01T00:00:00'}).status_code == 422


def test_inventory_scoped_preserves_history(client):
    before = client.get('/api/analytics/overview').json()['data']
    assert client.patch('/api/inventory/inv1',json={'stock_quantity':0}).status_code == 200
    assert 'p1' not in [a['product_id'] for a in client.get('/api/ads/recommendations?q=шампунь').json()['data']]
    after = client.get('/api/analytics/overview').json()['data']
    for k in ['impressions','clicks','confirmed_purchases','revenue','spend']:
        assert before[k] == after[k]
    assert client.patch('/api/discounts/d1',json={'active':True}).status_code == 409
    assert client.patch('/api/discounts/d1',json={'active':False}).status_code == 200
    assert client.patch('/api/inventory/inv1',json={'stock_quantity':-1}).status_code == 422
    assert client.patch('/api/inventory/inv1',json={'stock_quantity':1.5}).status_code == 422


def test_frontend_patch_atomic(client):
    data = client.patch('/api/products/p2',json={'product_id':'p2','percent':35,'active':True,'in_stock':True}).json()['data']
    assert data['current_price'] == 3640
    assert client.patch('/api/products/p2',json={'in_stock':False,'active':True}).status_code == 409
    assert next(p for p in client.get('/api/products').json()['data'] if p['product_id']=='p2')['in_stock']


def test_cors_health_openapi(client):
    assert client.get('/api/health').json()['data']['status'] == 'ok'
    response = client.options('/api/ads/click',headers={'Origin':'http://localhost:5500','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'Content-Type'})
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5500'
    denied = client.options('/api/ads/click',headers={'Origin':'https://unrelated.example','Access-Control-Request-Method':'POST'})
    assert 'access-control-allow-origin' not in denied.headers
    spec = client.get('/openapi.json').json()
    assert len(spec['paths']) >= 19
    assert client.get('/api/unknown').json()['error']['code'] == 'HTTP_ERROR'
