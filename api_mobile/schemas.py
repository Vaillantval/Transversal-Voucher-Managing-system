from decimal import Decimal
from typing import List, Optional
from datetime import datetime

from ninja import Schema


# ── Auth ─────────────────────────────────────────────────────────────────────

class GoogleAuthIn(Schema):
    id_token: str
    platform: str  # 'android' | 'ios'

class RefreshIn(Schema):
    refresh_token: str

class UserOut(Schema):
    id: int
    email: str
    full_name: str
    avatar_url: str
    phone: str
    notif_promo: bool
    notif_transac: bool
    created_at: datetime

class AuthOut(Schema):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    user: UserOut

class AccessTokenOut(Schema):
    access_token: str
    token_type: str = 'bearer'

class DeviceTokenIn(Schema):
    fcm_token: str
    platform: str  # 'android' | 'ios'

class OkOut(Schema):
    ok: bool = True


# ── Account ───────────────────────────────────────────────────────────────────

class AccountPatchIn(Schema):
    phone: Optional[str] = None
    notif_promo: Optional[bool] = None
    notif_transac: Optional[bool] = None


# ── Store ─────────────────────────────────────────────────────────────────────

class BannerOut(Schema):
    id: int
    title: str
    subtitle: str
    image_url: str
    cta_text: str

class SiteOut(Schema):
    id: int
    name: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]

class TierOut(Schema):
    id: int
    label: str
    duration_minutes: int
    duration_display: str
    price_htg: Decimal


# ── Orders ────────────────────────────────────────────────────────────────────

class CheckoutItemIn(Schema):
    tier_id: int
    quantity: int

class CheckoutIn(Schema):
    site_id: int
    items: List[CheckoutItemIn]
    payment_method: str = 'moncash'   # 'moncash' | 'natcash'
    full_name: str
    phone: str

class CheckoutOut(Schema):
    order_ref: str
    payment_url: str

class OrderStatusOut(Schema):
    status: str
    voucher_codes: List[str]

class OrderItemOut(Schema):
    tier_label: str
    site_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    voucher_codes: List[str]

class OrderSummaryOut(Schema):
    reference: str
    created_at: datetime
    status: str
    total_htg: Decimal
    items_count: int

class OrderDetailOut(Schema):
    reference: str
    created_at: datetime
    status: str
    total_htg: Decimal
    payment_method: str
    items: List[OrderItemOut]

class PaginatedOrdersOut(Schema):
    count: int
    page: int
    page_size: int
    results: List[OrderSummaryOut]
