from rest_framework.routers import DefaultRouter
from .airline import AirlineFinanceViewSet

from .views import (
    ExchangeRateViewSet,
    AgencyCashEntryViewSet,
    ExpensePaymentViewSet,
    FinancialTransactionViewSet,
    TripExpenseViewSet,
)

router = DefaultRouter()
router.register("airlines", AirlineFinanceViewSet, basename="airline-finance")
router.register("exchange-rates", ExchangeRateViewSet, basename="exchange-rate")
router.register("transactions", FinancialTransactionViewSet, basename="financial-transaction")
router.register("expenses", TripExpenseViewSet, basename="trip-expense")
router.register("expense-payments", ExpensePaymentViewSet, basename="expense-payment")
router.register("cash-entries", AgencyCashEntryViewSet, basename="agency-cash-entry")

urlpatterns = router.urls
