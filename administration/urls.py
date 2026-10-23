from django.urls import path
from .views import (
    dashboard_view,
    customers_list_view,
    customer_toggle_pro_view,
    customer_toggle_status_view,
    transactions_list_view,
    announcements_view,
    announcement_create_view,
    announcement_toggle_view,
)

app_name = 'administration'

urlpatterns = [
    # Dashboard Geral
    path('', dashboard_view, name='dashboard'),

    # Gestão de Clientes
    path('customers/', customers_list_view, name='customers'),
    path('customers/<uuid:user_id>/toggle-pro/', customer_toggle_pro_view, name='customer_toggle_pro'),
    path('customers/<uuid:user_id>/toggle-status/', customer_toggle_status_view, name='customer_toggle_status'),

    # Financeiro e Transações
    path('transactions/', transactions_list_view, name='transactions'),

    # Avisos do Sistema
    path('announcements/', announcements_view, name='announcements'),
    path('announcements/create/', announcement_create_view, name='announcement_create'),
    path('announcements/<uuid:announcement_id>/toggle/', announcement_toggle_view, name='announcement_toggle'),
]
