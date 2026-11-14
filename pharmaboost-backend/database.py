"""SQLite configuration and request-scoped units of work."""
import os
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def utcnow() -> datetime:
    """Store UTC without tzinfo (SQLite has no timezone-aware datetime type)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('Укажите часовой пояс даты (Z или +05:00)')
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if not url.startswith('sqlite:'):
        raise ValueError('Этот проект поддерживает только SQLite')
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15})

    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, _):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=15000')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()

    return engine


DEFAULT_DB = Path(__file__).resolve().parent / 'pharmaboost.db'
engine = make_engine(os.getenv('DATABASE_URL', f'sqlite:///{DEFAULT_DB.as_posix()}'))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        session.execute(text('BEGIN'))  # one consistent snapshot for multi-query analytics
        yield session


def get_write_db():
    # Acquire the SQLite writer lock BEFORE reads: duplicate IDs, budget and stock
    # checks then commit atomically, including simultaneous requests/processes.
    with SessionLocal() as session:
        try:
            session.execute(text('BEGIN IMMEDIATE'))
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
