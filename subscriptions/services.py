import stripe
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Plan, PlanPrice, Subscription, SubscriptionStatus, BillingInterval, PaymentTransaction
from accounts.models import User, Currency


def ensure_default_plans():
    """Garante a existência dos planos Gratuito e Pro com suas tabelas de preços em BRL, USD e EUR."""
    # 1. Plano Gratuito (Starter)
    free_plan, _ = Plan.objects.get_or_create(
        code='free',
        defaults={
            'name': 'Plano Gratuito',
            'description': 'Todos os recursos essenciais de anotações com limite de até 50 notas ativas.',
            'max_notes': 50,
            'is_active': True,
        }
    )

    # 2. Plano Pro (Ilimitado)
    pro_plan, _ = Plan.objects.get_or_create(
        code='pro',
        defaults={
            'name': 'Plano Pro Ilimitado',
            'description': 'Notas e cadernos ilimitados, histórico de versões estendido e anexos maiores.',
            'max_notes': None,
            'is_active': True,
        }
    )

    # Preços pré-definidos para o Plano Pro nas 3 moedas
    pricing_matrix = [
        # BRL (Real Brasileiro)
        (Currency.BRL, BillingInterval.MONTHLY, Decimal('9.90')),
        (Currency.BRL, BillingInterval.YEARLY, Decimal('79.90')),
        (Currency.BRL, BillingInterval.LIFETIME, Decimal('149.00')),
        # USD (Dólar Americano)
        (Currency.USD, BillingInterval.MONTHLY, Decimal('1.99')),
        (Currency.USD, BillingInterval.YEARLY, Decimal('14.99')),
        (Currency.USD, BillingInterval.LIFETIME, Decimal('29.99')),
        # EUR (Euro)
        (Currency.EUR, BillingInterval.MONTHLY, Decimal('1.99')),
        (Currency.EUR, BillingInterval.YEARLY, Decimal('14.99')),
        (Currency.EUR, BillingInterval.LIFETIME, Decimal('29.99')),
    ]

    for curr, interval, amount in pricing_matrix:
        PlanPrice.objects.get_or_create(
            plan=pro_plan,
            currency=curr,
            interval=interval,
            defaults={'amount': amount}
        )

    return free_plan, pro_plan


def create_stripe_checkout_session(user, plan_price, success_url, cancel_url):
    """
    Cria uma sessão oficial no Stripe Checkout adaptada à moeda escolhida.
    Caso as chaves da Stripe não estejam configuradas em desenvolvimento,
    retorna URL simulada para testes locais seguros.
    """
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

    if not stripe_key:
        # Modo de desenvolvimento sem chave Stripe real configurada:
        # Retorna URL de simulação imediata
        return {
            'mode': 'simulation',
            'url': f"{success_url}?mock_price_id={plan_price.id}",
            'id': 'cs_mock_test_session',
        }

    stripe.api_key = stripe_key

    mode = 'payment' if plan_price.interval == BillingInterval.LIFETIME else 'subscription'
    currency_code = plan_price.currency.lower()
    unit_amount_cents = int(plan_price.amount * 100)

    # Cria ou busca Stripe Customer
    customer_id = None
    if hasattr(user, 'subscription') and user.subscription.stripe_customer_id:
        customer_id = user.subscription.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or user.email,
            metadata={'user_id': str(user.id)}
        )
        customer_id = customer.id

    line_items = []
    if plan_price.stripe_price_id:
        line_items.append({'price': plan_price.stripe_price_id, 'quantity': 1})
    else:
        # Preço dinâmico inline
        price_data = {
            'currency': currency_code,
            'unit_amount': unit_amount_cents,
            'product_data': {
                'name': f"skdnote Pro — {plan_price.get_interval_display()}",
                'description': "Notas ilimitadas e sincronização contínua",
            },
        }
        if mode == 'subscription':
            interval_str = 'month' if plan_price.interval == BillingInterval.MONTHLY else 'year'
            price_data['recurring'] = {'interval': interval_str}

        line_items.append({'price_data': price_data, 'quantity': 1})

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=line_items,
        mode=mode,
        success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=cancel_url,
        client_reference_id=str(user.id),
        metadata={
            'user_id': str(user.id),
            'plan_price_id': str(plan_price.id),
            'currency': plan_price.currency,
            'interval': plan_price.interval,
        }
    )

    return {
        'mode': 'live',
        'url': session.url,
        'id': session.id,
    }


def activate_user_pro_subscription(user, plan_price, stripe_customer_id="", stripe_sub_id=None):
    """Ativa ou atualiza o usuário para o Plano Pro com notas ilimitadas."""
    pro_plan = Plan.objects.filter(code='pro').first()
    if not pro_plan:
        _, pro_plan = ensure_default_plans()

    # Define período (1 mês, 1 ano ou 100 anos para vitalício)
    now = timezone.now()
    if plan_price.interval == BillingInterval.MONTHLY:
        period_end = now + timezone.timedelta(days=32)
    elif plan_price.interval == BillingInterval.YEARLY:
        period_end = now + timezone.timedelta(days=366)
    else:
        period_end = now + timezone.timedelta(days=36500)  # Vitalício

    subscription, created = Subscription.objects.update_or_create(
        user=user,
        defaults={
            'plan': pro_plan,
            'currency': plan_price.currency,
            'interval': plan_price.interval,
            'stripe_customer_id': stripe_customer_id,
            'stripe_subscription_id': stripe_sub_id,
            'status': SubscriptionStatus.ACTIVE,
            'current_period_end': period_end,
            'cancel_at_period_end': False,
        }
    )

    # Registra transação financeira
    PaymentTransaction.objects.create(
        user=user,
        amount=plan_price.amount,
        currency=plan_price.currency,
        status='succeeded'
    )

    return subscription


def create_stripe_customer_portal(user, return_url):
    """Gera URL de sessão segura no portal de autoatendimento da Stripe."""
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if not stripe_key:
        return return_url

    stripe.api_key = stripe_key
    subscription = getattr(user, 'subscription', None)
    if not subscription or not subscription.stripe_customer_id:
        return return_url

    session = stripe.billing_portal.Session.create(
        customer=subscription.stripe_customer_id,
        return_url=return_url
    )
    return session.url
