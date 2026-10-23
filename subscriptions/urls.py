from django.urls import path
from .views import (
    pricing_view,
    checkout_view,
    checkout_success_view,
    checkout_cancel_view,
    billing_portal_view,
    stripe_webhook_view,
)

app_name = 'subscriptions'

urlpatterns = [
    # Tabela de Preços e Moedas
    path('pricing/', pricing_view, name='pricing'),

    # Fluxo Stripe Checkout
    path('checkout/', checkout_view, name='checkout'),
    path('checkout/success/', checkout_success_view, name='checkout_success'),
    path('checkout/cancel/', checkout_cancel_view, name='checkout_cancel'),

    # Stripe Customer Portal (Cancelamento e Gestão de Cartões)
    path('portal/', billing_portal_view, name='billing_portal'),

    # Webhooks da Stripe (Idempotente e Seguro)
    path('webhooks/stripe/', stripe_webhook_view, name='stripe_webhook'),
]
