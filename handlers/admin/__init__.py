from .customers import router as customers_router
from .debts import router as debts_router
from .stats import router as stats_router

__all__ = ["customers_router", "debts_router", "stats_router"]

