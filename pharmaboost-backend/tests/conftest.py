import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['AUTO_SEED'] = 'false'
from database import Base, make_engine, get_db, get_write_db
from main import create_app
from seed import seed_database


@pytest.fixture(scope='session')
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp('seed') / 'template.db'
    engine = make_engine(f'sqlite:///{path.as_posix()}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    assert seed_database(factory)
    engine.dispose()  # close/checkpoint WAL before copying
    return path


@pytest.fixture
def factory(tmp_path, template_db):
    path = tmp_path / 'test.db'
    shutil.copyfile(template_db, path)
    engine = make_engine(f'sqlite:///{path.as_posix()}')
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(factory, monkeypatch):
    monkeypatch.setenv('DEMO_ENABLED', 'true')
    app = create_app(initialize=False)

    def read_db():
        with factory() as session:
            yield session

    def write_db():
        with factory() as session:
            try:
                session.execute(text('BEGIN IMMEDIATE'))
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = read_db
    app.dependency_overrides[get_write_db] = write_db
    with TestClient(app) as test_client:
        yield test_client


def event_chain(client, suffix='1', campaign='c1', product='p1'):
    imp = client.post('/api/ads/impression', json={'impression_id':f'i-test-{suffix}', 'campaign_id':campaign,
                                                  'product_id':product, 'query':'Шампунь', 'is_demo':True})
    assert imp.status_code == 200, imp.text
    click = client.post('/api/ads/click', json={'click_id':f'k-test-{suffix}', 'impression_id':imp.json()['data']['impression_id'], 'is_demo':True})
    assert click.status_code == 200, click.text
    return imp.json()['data'], click.json()['data']
