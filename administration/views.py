from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from accounts.models import User, UserType
from subscriptions.models import Subscription, SubscriptionStatus, Plan, PaymentTransaction
from core.models import SystemAnnouncement
from .decorators import admin_required
from .services import get_saas_metrics


@admin_required
def dashboard_view(request):
    """
    Dashboard principal executivo com métricas SaaS multi-moeda,
    taxa de conversão e oportunidades quentes de upgrade.
    """
    metrics = get_saas_metrics()
    recent_transactions = PaymentTransaction.objects.select_related('user').order_by('-created_at')[:5]
    recent_announcements = SystemAnnouncement.objects.order_by('-created_at')[:3]

    context = {
        'user': request.user,
        'metrics': metrics,
        'recent_transactions': recent_transactions,
        'recent_announcements': recent_announcements,
        'active_menu': 'dashboard',
    }
    return render(request, 'administration/dashboard.html', context)


@admin_required
def customers_list_view(request):
    """
    Gestão completa de clientes com busca, filtros de status e ações de suporte.
    """
    search_q = request.GET.get('q', '').strip()
    plan_filter = request.GET.get('plan', 'all')
    status_filter = request.GET.get('status', 'all')

    customers_qs = User.objects.filter(role=UserType.CUSTOMER)\
        .annotate(active_notes_count=Count('notes', filter=Q(notes__is_deleted=False)))\
        .select_related('subscription', 'subscription__plan')\
        .order_by('-created_at')

    if search_q:
        customers_qs = customers_qs.filter(
            Q(email__icontains=search_q) | Q(full_name__icontains=search_q)
        )

    if plan_filter == 'pro':
        customers_qs = customers_qs.filter(
            subscription__status=SubscriptionStatus.ACTIVE,
            subscription__plan__code='pro'
        )
    elif plan_filter == 'free':
        customers_qs = customers_qs.exclude(
            subscription__status=SubscriptionStatus.ACTIVE,
            subscription__plan__code='pro'
        )

    if status_filter == 'active':
        customers_qs = customers_qs.filter(is_active=True)
    elif status_filter == 'suspended':
        customers_qs = customers_qs.filter(is_active=False)

    customers = list(customers_qs)

    context = {
        'customers': customers,
        'search_q': search_q,
        'plan_filter': plan_filter,
        'status_filter': status_filter,
        'active_menu': 'customers',
    }
    return render(request, 'administration/customers.html', context)


@admin_required
@require_POST
def customer_toggle_pro_view(request, user_id):
    """
    Ação de suporte: Concede ou revoga manualmente o Plano Pro (cortesia / VIP).
    """
    target_user = get_object_or_404(User, id=user_id, role=UserType.CUSTOMER)
    pro_plan = Plan.objects.filter(code='pro').first()
    free_plan = Plan.objects.filter(code='free').first()

    subscription = getattr(target_user, 'subscription', None)

    if subscription and subscription.is_pro:
        # Revoga Pro e rebaixa para Gratuito
        subscription.plan = free_plan
        subscription.save(update_fields=['plan', 'updated_at'])
    else:
        # Concede Plano Pro cortesia
        if subscription:
            subscription.plan = pro_plan
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_end = timezone.now() + timezone.timedelta(days=365)
            subscription.save(update_fields=['plan', 'status', 'current_period_end', 'updated_at'])
        else:
            Subscription.objects.create(
                user=target_user,
                plan=pro_plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_end=timezone.now() + timezone.timedelta(days=365)
            )

    return redirect('administration:customers')


@admin_required
@require_POST
def customer_toggle_status_view(request, user_id):
    """
    Ação de suporte: Suspende ou reativa o acesso de um cliente.
    """
    target_user = get_object_or_404(User, id=user_id, role=UserType.CUSTOMER)
    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active', 'updated_at'])
    return redirect('administration:customers')


@admin_required
def transactions_list_view(request):
    """
    Histórico financeiro completo e auditoria de pagamentos multi-moeda.
    """
    transactions = PaymentTransaction.objects.select_related('user').order_by('-created_at')
    
    context = {
        'transactions': transactions,
        'active_menu': 'transactions',
    }
    return render(request, 'administration/transactions.html', context)


@admin_required
def announcements_view(request):
    """
    Gestão de avisos e notificações globais do sistema.
    """
    announcements = SystemAnnouncement.objects.order_by('-created_at')

    context = {
        'announcements': announcements,
        'active_menu': 'announcements',
    }
    return render(request, 'administration/announcements.html', context)


@admin_required
@require_POST
def announcement_create_view(request):
    """
    Criação de um novo aviso global no sistema.
    """
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    level = request.POST.get('level', SystemAnnouncement.Level.INFO)

    if title and message:
        SystemAnnouncement.objects.create(
            title=title,
            message=message,
            level=level,
            is_active=True
        )

    return redirect('administration:announcements')


@admin_required
@require_POST
def announcement_toggle_view(request, announcement_id):
    """
    Ativa ou desativa um aviso global do sistema.
    """
    announcement = get_object_or_404(SystemAnnouncement, id=announcement_id)
    announcement.is_active = not announcement.is_active
    announcement.save(update_fields=['is_active', 'updated_at'])
    return redirect('administration:announcements')
