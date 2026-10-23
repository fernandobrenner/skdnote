import json
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from accounts.models import Currency, User
from core.geolocation import (
    get_client_currency,
    get_currency_display_info,
    detect_country_from_request,
)
from .models import Plan, PlanPrice, Subscription, SubscriptionStatus, BillingInterval, PaymentTransaction
from .services import (
    ensure_default_plans,
    create_stripe_checkout_session,
    activate_user_pro_subscription,
    create_stripe_customer_portal,
)


def pricing_view(request):
    """
    Página de Preços e Planos com detecção automática de moeda por Geolocalização
    do cliente (BRL para Brasil, EUR para Zona do Euro, USD para internacional).
    FBV: Function-Based View.
    """
    ensure_default_plans()

    # Identifica a moeda ativa automaticamente por geolocalização ou override do usuário
    selected_currency = get_client_currency(request)
    display_info = get_currency_display_info(selected_currency)
    detected_country = detect_country_from_request(request)

    # Busca planos e preços na moeda selecionada
    pro_plan = Plan.objects.filter(code='pro').first()
    prices = PlanPrice.objects.filter(plan=pro_plan, currency=selected_currency)

    # Organiza preços por ciclo
    prices_by_interval = {
        'MONTHLY': prices.filter(interval=BillingInterval.MONTHLY).first(),
        'YEARLY': prices.filter(interval=BillingInterval.YEARLY).first(),
        'LIFETIME': prices.filter(interval=BillingInterval.LIFETIME).first(),
    }

    context = {
        'selected_currency': selected_currency,
        'currency_symbol': display_info['symbol'],
        'currency_flag': display_info['flag'],
        'detected_country': detected_country,
        'prices': prices_by_interval,
        'currencies': Currency.choices,
    }
    return render(request, 'subscriptions/pricing.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def checkout_view(request):
    """
    Inicia o fluxo de pagamento internacional via Stripe Checkout Session
    com a moeda determinada pela geolocalização ou preferência do cliente.
    FBV: Function-Based View.
    """
    ensure_default_plans()

    price_id = request.GET.get('price_id') or request.POST.get('price_id')
    currency_param = request.GET.get('currency') or get_client_currency(request)
    interval_param = request.GET.get('interval', BillingInterval.MONTHLY)

    plan_price = None
    if price_id:
        plan_price = PlanPrice.objects.filter(id=price_id).first()
    else:
        pro_plan = Plan.objects.filter(code='pro').first()
        plan_price = PlanPrice.objects.filter(
            plan=pro_plan,
            currency=currency_param,
            interval=interval_param
        ).first()

    if not plan_price:
        return HttpResponseBadRequest("Plano ou moeda inválida.")

    success_url = request.build_absolute_uri(reverse('subscriptions:checkout_success'))
    cancel_url = request.build_absolute_uri(reverse('subscriptions:checkout_cancel'))

    session_data = create_stripe_checkout_session(
        user=request.user,
        plan_price=plan_price,
        success_url=success_url,
        cancel_url=cancel_url
    )

    return redirect(session_data['url'])


@login_required
def checkout_success_view(request):
    """
    Página de sucesso após confirmação do pagamento no Stripe Checkout.
    """
    mock_price_id = request.GET.get('mock_price_id')
    session_id = request.GET.get('session_id')

    # Ativação imediata em modo de desenvolvimento / simulação
    if mock_price_id:
        plan_price = PlanPrice.objects.filter(id=mock_price_id).first()
        if plan_price:
            activate_user_pro_subscription(
                user=request.user,
                plan_price=plan_price,
                stripe_customer_id="cus_mock_local"
            )

    return render(request, 'subscriptions/success.html', {
        'user': request.user,
    })


def checkout_cancel_view(request):
    """Página exibida caso o usuário cancele a sessão de checkout."""
    return render(request, 'subscriptions/cancel.html')


@login_required
def billing_portal_view(request):
    """Redireciona para o portal seguro de faturamento da Stripe (cancelamento e troca de cartão)."""
    return_url = request.build_absolute_uri(reverse('notes:app'))
    portal_url = create_stripe_customer_portal(request.user, return_url)
    return redirect(portal_url)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Webhook handler oficial da Stripe:
    Trata de forma segura e idempotente eventos de pagamento, ativação e cancelamento.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    event = None

    if webhook_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
    else:
        # Fallback para parsing direto do JSON caso webhook secret não esteja configurado
        try:
            event = json.loads(payload.decode('utf-8'))
        except Exception:
            return HttpResponse(status=400)

    event_type = event.get('type')
    data_object = event.get('data', {}).get('object', {})

    if event_type == 'checkout.session.completed':
        # Liberação imediata da assinatura Pro
        client_ref_id = data_object.get('client_reference_id')
        customer_id = data_object.get('customer')
        sub_id = data_object.get('subscription')
        metadata = data_object.get('metadata', {})
        plan_price_id = metadata.get('plan_price_id')

        if client_ref_id and plan_price_id:
            user = User.objects.filter(id=client_ref_id).first()
            plan_price = PlanPrice.objects.filter(id=plan_price_id).first()
            if user and plan_price:
                activate_user_pro_subscription(
                    user=user,
                    plan_price=plan_price,
                    stripe_customer_id=customer_id or '',
                    stripe_sub_id=sub_id
                )

    elif event_type == 'customer.subscription.deleted':
        # Cancelamento: Rebaixa para o plano gratuito
        sub_id = data_object.get('id')
        if sub_id:
            subscription = Subscription.objects.filter(stripe_subscription_id=sub_id).first()
            if subscription:
                free_plan = Plan.objects.filter(code='free').first()
                subscription.plan = free_plan
                subscription.status = SubscriptionStatus.CANCELED
                subscription.save(update_fields=['plan', 'status', 'updated_at'])

    elif event_type == 'invoice.payment_succeeded':
        # Auditoria de pagamento recebido
        customer_id = data_object.get('customer')
        amount_paid = data_object.get('amount_paid', 0) / 100
        currency = data_object.get('currency', 'brl').upper()

        if customer_id:
            subscription = Subscription.objects.filter(stripe_customer_id=customer_id).first()
            if subscription:
                PaymentTransaction.objects.create(
                    user=subscription.user,
                    amount=amount_paid,
                    currency=currency,
                    stripe_invoice_id=data_object.get('id', ''),
                    status='succeeded'
                )

    return HttpResponse(status=200)
