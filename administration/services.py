from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from accounts.models import User, UserType, Currency
from subscriptions.models import Subscription, SubscriptionStatus, PaymentTransaction, Plan
from notes.models import Note


def get_saas_metrics():
    """
    Consolida métricas executivas, faturamento multi-moeda e leads de conversão.
    """
    now = timezone.now()
    seven_days_ago = now - timezone.timedelta(days=7)
    thirty_days_ago = now - timezone.timedelta(days=30)

    # 1. Faturamento por Moeda
    tx_succeeded = PaymentTransaction.objects.filter(status='succeeded')
    revenue_brl = tx_succeeded.filter(currency=Currency.BRL).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_usd = tx_succeeded.filter(currency=Currency.USD).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_eur = tx_succeeded.filter(currency=Currency.EUR).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 2. Contagem e Segmentação de Clientes
    total_customers = User.objects.filter(role=UserType.CUSTOMER).count()
    active_pro_subs = Subscription.objects.filter(status=SubscriptionStatus.ACTIVE, plan__code='pro')
    pro_customers = active_pro_subs.count()
    free_customers = max(0, total_customers - pro_customers)

    conversion_rate = 0.0
    if total_customers > 0:
        conversion_rate = round((pro_customers / total_customers) * 100, 1)

    # 3. Novos Clientes
    new_customers_7d = User.objects.filter(role=UserType.CUSTOMER, created_at__gte=seven_days_ago).count()
    new_customers_30d = User.objects.filter(role=UserType.CUSTOMER, created_at__gte=thirty_days_ago).count()

    # 4. Volumetria de Notas
    total_notes = Note.objects.count()
    active_notes = Note.objects.filter(is_deleted=False).count()
    trashed_notes = Note.objects.filter(is_deleted=True).count()

    # 5. Oportunidades Quentes (Leads prestes a estourar o limite de 50 notas no plano gratuito)
    # Busca usuários clientes que têm entre 35 e 50 notas ativas
    hot_leads_qs = User.objects.filter(role=UserType.CUSTOMER)\
        .annotate(active_notes_count=Count('notes', filter=Q(notes__is_deleted=False)))\
        .filter(active_notes_count__gte=35, active_notes_count__lte=50)\
        .exclude(subscription__status=SubscriptionStatus.ACTIVE, subscription__plan__code='pro')\
        .order_by('-active_notes_count')[:10]

    hot_leads = [
        {
            'user': u,
            'notes_count': u.active_notes_count,
            'percentage': int((u.active_notes_count / 50) * 100)
        }
        for u in hot_leads_qs
    ]

    return {
        'revenue': {
            'brl': revenue_brl,
            'usd': revenue_usd,
            'eur': revenue_eur,
        },
        'customers': {
            'total': total_customers,
            'free': free_customers,
            'pro': pro_customers,
            'conversion_rate': conversion_rate,
            'new_7d': new_customers_7d,
            'new_30d': new_customers_30d,
        },
        'notes': {
            'total': total_notes,
            'active': active_notes,
            'trashed': trashed_notes,
        },
        'hot_leads': hot_leads,
    }
