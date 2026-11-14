"""Idempotent, atomic seed. All history is synthetic and marked as demo."""
from datetime import timedelta
from sqlalchemy import select, text
from database import Base, engine, SessionLocal, utcnow
from models import Product, Pharmacy, Inventory, Discount, AdCampaign, AdImpression, AdClick, Order

CATALOG = [
    ('Шампунь Daily Balance', 'Уход за волосами', 4800, ['шампунь', 'волосы'], 'BOTANICA'),
    ('Шампунь Gentle Care', 'Уход за волосами', 5600, ['шампунь', 'волосы', 'мягкий'], 'PURE LAB'),
    ('Шампунь Fresh Ritual', 'Уход за волосами', 3900, ['шампунь', 'волосы'], 'NATURALIST'),
    ('Солнцезащитный крем SPF 50', 'Солнцезащитные средства', 7200, ['солнцезащитный крем', 'солнце', 'защита от солнца'], 'SUN THEORY'),
    ('Крем для рук Soft Touch', 'Уход за кожей', 2400, ['крем для рук', 'руки', 'увлажнение'], 'BOTANICA'),
    ('Зубная паста Everyday', 'Гигиена', 1800, ['зубная паста', 'гигиена'], 'PURE LAB'),
    ('Сыворотка с витамином C', 'Уход за кожей', 6400, ['витамин с', 'сыворотка', 'кожа'], 'BOTANICA'),
    ('Витамин C Daily', 'Витамины и добавки', 3200, ['витамин с', 'витамин', 'добавки'], 'VITAFORM'),
    ('Бальзам для волос Silk', 'Уход за волосами', 4200, ['бальзам', 'волосы'], 'PURE LAB'),
    ('Гель для душа Morning', 'Гигиена', 2100, ['гель', 'душ', 'гигиена'], 'AQUAFORM'),
    ('Крем для лица Cloud', 'Уход за кожей', 5700, ['крем для лица', 'лицо', 'увлажнение'], 'NATURALIST'),
    ('Солнцезащитный флюид SPF 30', 'Солнцезащитные средства', 6100, ['солнцезащитный', 'солнце', 'флюид'], 'SUN THEORY'),
    ('Шампунь Urban Fresh', 'Уход за волосами', 3600, ['шампунь', 'волосы'], 'URBAN LEAF'),
    ('Витамин D Daily', 'Витамины и добавки', 2900, ['витамин д', 'витамин d', 'добавки'], 'VITAFORM'),
    ('Мицеллярная вода Clear', 'Уход за кожей', 3400, ['мицеллярная', 'вода', 'кожа'], 'PURE LAB'),
    ('Зубная щётка Soft', 'Гигиена', 1200, ['зубная щетка', 'гигиена'], 'AQUAFORM'),
    ('Бальзам для губ SPF 20', 'Солнцезащитные средства', 1900, ['губы', 'солнцезащитный', 'бальзам'], 'SUN THEORY'),
    ('Добавка Zinc Daily', 'Витамины и добавки', 3700, ['цинк', 'zinc', 'добавки'], 'VITAFORM'),
    ('Мыло для рук Pure', 'Гигиена', 900, ['мыло', 'руки', 'гигиена'], 'AQUAFORM'),
    ('Маска для волос Ritual', 'Уход за волосами', 4500, ['маска', 'волосы'], 'NATURALIST'),
]


def seed_database(factory=SessionLocal) -> bool:
    with factory() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        if db.scalar(select(Product.id).limit(1)):
            db.rollback()
            return False  # never overwrite an existing team's data
        now = utcnow()
        for index, name in enumerate(['Аптека Green', 'Аптека City', 'Аптека Orbit'], 1):
            db.add(Pharmacy(id=f'ph{index}', name=name, active=True))
        db.flush()
        for index, (name, category, price, keywords, brand) in enumerate(CATALOG, 1):
            product_id = f'p{index}'
            pharmacy_id = f'ph{1 if index in (1,2,5,7) else (index-1)%3+1}'
            p = Product(id=product_id, name=name, category=category, price=price*100,
                        description='Вымышленный демонстрационный товар. Без лечебных обещаний.', image_url='', active=True,
                        ad_allowed=True, brand=brand, keywords=keywords, volume='250 мл' if 'волосами' in category else '1 уп.',
                        shape='bottle' if index%2 else 'tube', color=['mint','blue','peach','yellow'][(index-1)%4])
            db.add(p)
            db.flush()
            db.add(Inventory(id=f'inv{index}', product_id=product_id, pharmacy_id=pharmacy_id,
                             stock_quantity=0 if index in (3,18) else 40+index, updated_at=now))
            db.flush()
            percent = [10,5,25,15,20,0,10,5,15,30][(index-1)%10]
            d = Discount(id=f'd{index}', product_id=product_id, pharmacy_id=pharmacy_id,
                         discount_percent=percent, active=index != 2,
                         start_date=now-timedelta(days=20), end_date=now+timedelta(days=30))
            if index == 7:
                d.end_date = now-timedelta(days=1)
            if index == 14:
                d.start_date, d.end_date = now+timedelta(days=3), now+timedelta(days=10)
            db.add(d)
            if index > 16:
                continue
            c = AdCampaign(id=f'c{index}', product_id=product_id, pharmacy_id=pharmacy_id, name=name,
                           budget=(80000+index*5000)*100, spent=0, cpc=(35+index*3)*100,
                           status='active' if index <= 15 else 'paused', created_at=now-timedelta(days=40))
            db.add(c)
            db.flush()
            for day in range(14):
                anchor = now-timedelta(days=13-day, hours=1)
                for position in range(40):
                    key = f'seed-{index}-{day}-{position}'
                    # Poor historical quality is intentionally present to explain WAI.
                    low = position % (3 if index in (3,9) else 8 if day<7 else 15) == 0
                    available = position % (6 if day<7 else 17) != 0
                    advertised = position % 2 == 0
                    valid = not advertised or position % (10 if day<7 else 20) != 0
                    created = anchor+timedelta(seconds=position*4)
                    imp = AdImpression(id=f'i-{key}', campaign_id=c.id, product_id=p.id, pharmacy_id=pharmacy_id,
                                       search_query=keywords[0], relevance_score=0.4 if low else 0.95,
                                       product_available=available, valid_discount=valid, discount_advertised=advertised,
                                       advertised_discount_percent=10 if advertised else 0, is_demo=True,
                                       request_fingerprint='seed', created_at=created)
                    db.add(imp)
                    db.flush()
                    if position % (4 if day>=7 else 5) != 0:
                        continue
                    click = AdClick(id=f'k-{key}', impression_id=imp.id, campaign_id=c.id, product_id=p.id,
                                    pharmacy_id=pharmacy_id, charged_cpc=c.cpc, request_fingerprint='seed',
                                    created_at=created+timedelta(seconds=1))
                    db.add(click)
                    c.spent += c.cpc
                    db.flush()
                    # Zero-conversion campaigns remain distinct from strong ones.
                    if index in (9,13) or position != (4 if day>=7 else 5) or day % (2 if index%3 else 4) != 0:
                        continue
                    confirmed = day % 5 != 0
                    order_time = created+timedelta(seconds=2)
                    db.add(Order(id=f'o-{key}', click_id=click.id, product_id=p.id, pharmacy_id=pharmacy_id,
                                 quantity=1, total_price=p.price, status='confirmed' if confirmed else 'cancelled',
                                 is_demo=True, confirmed_at=order_time if confirmed else None,
                                 request_fingerprint='seed', created_at=order_time))
            db.flush()
        db.commit()
        return True


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    print('Демонстрационные данные созданы.' if seed_database() else 'База уже заполнена: данные не изменены.')
