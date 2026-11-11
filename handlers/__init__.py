from .start import router as start_router
from .common import router as common_router
from .admin.customers import router as admin_customers_router
from .admin.debts import router as admin_debts_router
from .admin.stats import router as admin_stats_router
from .customer.my_debts import router as customer_debts_router

__all__ = [
    "start_router",
    "common_router",
    "admin_customers_router",
    "admin_debts_router",
    "admin_stats_router",
    "customer_debts_router"
]

