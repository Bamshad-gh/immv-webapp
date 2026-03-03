# payments/urls.py
# User-facing invoice URLs.
# Admin invoice management is under admin_panel/urls.py.

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('',          views.invoice_list,   name='invoice_list'),
    path('<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
]
