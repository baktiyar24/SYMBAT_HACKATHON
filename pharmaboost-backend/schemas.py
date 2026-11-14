"""Explicit request/response models. Public money is KZT; storage is integer tiyn."""
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar('T')
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')]
Percent = Annotated[int, Field(strict=True, ge=0, le=100)]


class Envelope(BaseModel, Generic[T]):
    data: T


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list | dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Health(BaseModel):
    status: str
    database: str
    demo_enabled: bool
    time: str


class PharmacyOut(BaseModel):
    id: str
    pharmacy_id: str
    name: str
    active: bool


class DiscountOut(BaseModel):
    id: str
    product_id: str
    pharmacy_id: str
    discount_percent: int
    percent: int  # frontend alias
    start_date: str
    end_date: str
    start_at: str
    end_at: str
    active: bool
    is_current: bool
    price: float
    new_price: float


class DiscountPatch(Input):
    discount_percent: Percent | None = Field(default=None, validation_alias=AliasChoices('discount_percent', 'percent'))
    start_date: datetime | None = None
    end_date: datetime | None = None
    active: bool | None = Field(default=None, strict=True)

    @field_validator('start_date', 'end_date')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Дата должна содержать часовой пояс')
        return value

    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set or any(getattr(self, k) is None for k in self.model_fields_set):
            raise ValueError('Передайте хотя бы одно изменяемое поле, без null')
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError('Дата окончания должна быть позже начала')
        return self


class InventoryOut(BaseModel):
    id: str
    product_id: str
    pharmacy_id: str
    stock_quantity: int
    updated_at: str


class InventoryPatch(Input):
    stock_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000)]


class ProductPatch(Input):
    product_id: Identifier | None = None
    pharmacy_id: Identifier | None = None
    percent: Percent | None = None
    active: bool | None = Field(default=None, strict=True)  # promotion, not product
    in_stock: bool | None = Field(default=None, strict=True)

    @model_validator(mode='after')
    def changed(self):
        fields = self.model_fields_set - {'product_id', 'pharmacy_id'}
        if not fields or any(getattr(self, k) is None for k in fields):
            raise ValueError('Укажите percent, active или in_stock без null')
        return self


class ProductOut(BaseModel):
    id: str
    product_id: str
    pharmacy_id: str
    inventory_id: str
    name: str
    category: str
    description: str
    image_url: str
    price: float
    current_price: float
    active: bool
    ad_allowed: bool
    in_stock: bool
    stock_quantity: int
    discount: DiscountOut | None
    effective_discount: int
    brand: str
    keywords: list[str]
    volume: str
    shape: str
    color: str
    pharmacy: str


class AdOut(ProductOut):
    campaign_id: str
    relevance_score: float
    discount_score: float
    performance_score: float
    smart_score: float
    reason: str
    performance_is_neutral: bool
    historical_clicks: int
    relevance: float
    performance: float
    score: float
    explanation: str


class ImpressionIn(Input):
    impression_id: Identifier
    campaign_id: Identifier
    product_id: Identifier
    pharmacy_id: Identifier | None = None
    search_query: str = Field(default='', max_length=200, validation_alias=AliasChoices('search_query', 'query'))
    advertised_discount_percent: Percent = 0
    is_demo: Literal[True] = True


class ImpressionOut(BaseModel):
    impression_id: str
    campaign_id: str
    product_id: str
    pharmacy_id: str
    search_query: str
    relevance_score: float
    product_available: bool
    valid_discount: bool
    discount_advertised: bool
    advertised_discount_percent: int
    is_demo: bool
    created_at: str


class ClickIn(Input):
    click_id: Identifier
    impression_id: Identifier
    campaign_id: Identifier | None = None
    product_id: Identifier | None = None
    pharmacy_id: Identifier | None = None
    is_demo: Literal[True] = True


class ClickOut(BaseModel):
    click_id: str
    impression_id: str
    campaign_id: str
    product_id: str
    pharmacy_id: str
    charged_cpc: float
    is_demo: bool
    created_at: str


class OrderIn(Input):
    order_id: Identifier
    click_id: Identifier | None = None
    product_id: Identifier
    pharmacy_id: Identifier | None = None
    quantity: Annotated[int, Field(strict=True, ge=1, le=100)] = 1
    confirm: bool = Field(default=True, strict=True, description='Явное синхронное подтверждение тестового заказа; false создаёт pending')
    is_demo: Literal[True] = True


class OrderOut(BaseModel):
    order_id: str
    click_id: str | None
    campaign_id: str | None
    product_id: str
    pharmacy_id: str
    quantity: int
    total_price: float
    amount: float
    status: Literal['pending', 'confirmed', 'cancelled']
    is_demo: bool
    created_at: str
    confirmed_at: str | None


class OrderStatusIn(Input):
    status: Literal['confirmed', 'cancelled']


class DailyAnalytics(BaseModel):
    date: str
    impressions: int
    clicks: int
    confirmed_purchases: int
    cancelled_orders: int
    relevant_impressions: int
    available_impressions: int
    problematic_impressions: int
    spend: float
    revenue: float


class Overview(BaseModel):
    impressions: int
    clicks: int
    confirmed_purchases: int
    cancelled_orders: int
    relevant_impressions: int
    available_impressions: int
    problematic_impressions: int
    spend: float
    revenue: float
    attributed_revenue: float
    ctr: float | None
    cpc: float | None
    cvr: float | None
    cpa: float | None
    roas: float | None
    rr: float
    ar: float
    rpi: float
    wai: float | None
    budget: float
    lifetime_spent: float
    active_campaigns: int
    available_products: int
    active_discounts: int
    daily: list[DailyAnalytics]
    period_start: str
    period_end: str
    scenario: str
    is_demo: bool
    attribution_days: int
    problem_reasons: dict[str, int]


class CampaignAnalytics(Overview):
    campaign_id: str
    product_id: str
    pharmacy_id: str
    name: str
    status: str


class RpiOut(BaseModel):
    rpi: float
    cvr: float  # fraction here; overview.cvr is percent
    relevance_rate: float
    availability_rate: float
    previous_rpi: float
    change_percent: float | None
    current: Overview
    baseline: Overview
    experimental: bool = True
    note: str


class WaiOut(BaseModel):
    wai: float | None
    problematic_impressions: int
    total_impressions: int
    reasons: dict[str, int]
    previous_wai: float | None
    change_percent: float | None
    change_percentage_points: float | None
    period_start: str
    period_end: str
    previous_period_start: str
    previous_period_end: str
    note: str


class RecommendationOut(BaseModel):
    id: str
    campaign_id: str
    product_id: str
    type: str
    priority: Literal['high', 'medium', 'low']
    title: str
    description: str
    action: str
    status: str
    text: str
