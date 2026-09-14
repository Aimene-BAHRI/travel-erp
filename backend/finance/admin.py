from django.contrib import admin

from .models import AgencyCashEntry, ExchangeRate, ExpensePayment, FinancialTransaction, TripExpense

admin.site.register(ExchangeRate)
admin.site.register(FinancialTransaction)
admin.site.register(TripExpense)
admin.site.register(ExpensePayment)
admin.site.register(AgencyCashEntry)
