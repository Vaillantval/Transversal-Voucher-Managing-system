from ninja import NinjaAPI

from .account import router as account_router
from .auth import router as auth_router
from .store import router as store_router
from .orders import router as orders_router

api = NinjaAPI(
    title='BonNet Mobile API',
    version='1.0.0',
    description="API REST pour l'application mobile BonNet",
    urls_namespace='api_mobile',
)

api.add_router('/auth/', auth_router)
api.add_router('/account/', account_router)
api.add_router('/store/', store_router)
api.add_router('', orders_router)
