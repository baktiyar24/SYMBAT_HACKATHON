from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(1000), default='')
    price: Mapped[int] = mapped_column(Integer)  # integer tiyn, never float
    image_url: Mapped[str] = mapped_column(String(500), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ad_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    brand: Mapped[str] = mapped_column(String(80), default='DEMO')
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    volume: Mapped[str] = mapped_column(String(40), default='1 шт.')
    shape: Mapped[str] = mapped_column(String(20), default='bottle')
    color: Mapped[str] = mapped_column(String(20), default='mint')
    __table_args__ = (CheckConstraint('price >= 0'),)


class Pharmacy(Base):
    __tablename__ = 'pharmacies'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Inventory(Base):
    __tablename__ = 'inventory'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'))
    pharmacy_id: Mapped[str] = mapped_column(ForeignKey('pharmacies.id', ondelete='RESTRICT'))
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('product_id', 'pharmacy_id'), CheckConstraint('stock_quantity >= 0'))


class Discount(Base):
    __tablename__ = 'discounts'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pharmacy_id: Mapped[str] = mapped_column(String(64))
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint('product_id', 'pharmacy_id'),
        ForeignKeyConstraint(['product_id', 'pharmacy_id'], ['inventory.product_id', 'inventory.pharmacy_id']),
        CheckConstraint('discount_percent BETWEEN 0 AND 100'), CheckConstraint('end_date > start_date'),
    )


class AdCampaign(Base):
    __tablename__ = 'ad_campaigns'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pharmacy_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    budget: Mapped[int] = mapped_column(Integer)
    spent: Mapped[int] = mapped_column(Integer, default=0)
    cpc: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(['product_id', 'pharmacy_id'], ['inventory.product_id', 'inventory.pharmacy_id']),
        UniqueConstraint('id', 'product_id', 'pharmacy_id'),
        CheckConstraint('budget >= 0 AND spent >= 0 AND spent <= budget AND cpc >= 0'),
        CheckConstraint("status IN ('active', 'paused', 'completed')"),
    )


class AdImpression(Base):
    __tablename__ = 'ad_impressions'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pharmacy_id: Mapped[str] = mapped_column(String(64))
    search_query: Mapped[str] = mapped_column(String(200), default='')
    relevance_score: Mapped[float]
    product_available: Mapped[bool] = mapped_column(Boolean)
    valid_discount: Mapped[bool] = mapped_column(Boolean)
    discount_advertised: Mapped[bool] = mapped_column(Boolean, default=False)
    advertised_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    __table_args__ = (
        ForeignKeyConstraint(['campaign_id', 'product_id', 'pharmacy_id'], ['ad_campaigns.id', 'ad_campaigns.product_id', 'ad_campaigns.pharmacy_id']),
        UniqueConstraint('id', 'campaign_id', 'product_id', 'pharmacy_id'),
        CheckConstraint('relevance_score BETWEEN 0 AND 1'),
        CheckConstraint('advertised_discount_percent BETWEEN 0 AND 100'),
    )


class AdClick(Base):
    __tablename__ = 'ad_clicks'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    impression_id: Mapped[str] = mapped_column(String(80), unique=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pharmacy_id: Mapped[str] = mapped_column(String(64))
    charged_cpc: Mapped[int] = mapped_column(Integer)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    __table_args__ = (
        ForeignKeyConstraint(['impression_id', 'campaign_id', 'product_id', 'pharmacy_id'], ['ad_impressions.id', 'ad_impressions.campaign_id', 'ad_impressions.product_id', 'ad_impressions.pharmacy_id']),
        UniqueConstraint('id', 'product_id', 'pharmacy_id'), CheckConstraint('charged_cpc >= 0'),
    )


class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    click_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pharmacy_id: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    __table_args__ = (
        ForeignKeyConstraint(['click_id', 'product_id', 'pharmacy_id'], ['ad_clicks.id', 'ad_clicks.product_id', 'ad_clicks.pharmacy_id']),
        ForeignKeyConstraint(['product_id', 'pharmacy_id'], ['inventory.product_id', 'inventory.pharmacy_id']),
        CheckConstraint('quantity > 0 AND total_price >= 0'),
        CheckConstraint("status IN ('pending', 'confirmed', 'cancelled')"),
        CheckConstraint("(status = 'confirmed' AND confirmed_at IS NOT NULL) OR (status != 'confirmed' AND confirmed_at IS NULL)"),
    )
