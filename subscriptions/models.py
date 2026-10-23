from django.db import models
from django.conf import settings
from core.models import UUIDModel, TimeStampedModel
from accounts.models import Currency


class BillingInterval(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Mensal'
    YEARLY = 'YEARLY', 'Anual'
    LIFETIME = 'LIFETIME', 'Vitalício (Pagamento Único)'


class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'active', 'Ativa'
    TRIALING = 'trialing', 'Período de Teste'
    PAST_DUE = 'past_due', 'Pagamento Pendente'
    CANCELED = 'canceled', 'Cancelada'
    INCOMPLETE = 'incomplete', 'Incompleta'


class Plan(UUIDModel, TimeStampedModel):
    """Plano de assinatura do sistema (ex: Gratuito vs Pro Ilimitado)."""
    name = models.CharField(max_length=100, verbose_name="Nome do Plano")
    code = models.CharField(max_length=50, unique=True, verbose_name="Código Identificador (slug)")
    description = models.TextField(blank=True, verbose_name="Descrição dos Benefícios")
    max_notes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite de Notas Ativas (nulo para ilimitado)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Disponível para Compra")

    class Meta:
        verbose_name = "Plano"
        verbose_name_plural = "Planos"
        ordering = ['max_notes']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_free(self):
        return self.code == 'free'

    @property
    def is_pro(self):
        return self.code == 'pro'


class PlanPrice(UUIDModel, TimeStampedModel):
    """Tabela de preços localizada por moeda (BRL, USD, EUR) e ciclo de cobrança."""
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='prices',
        verbose_name="Plano"
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.BRL,
        verbose_name="Moeda"
    )
    interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        verbose_name="Ciclo de Faturamento"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor"
    )
    stripe_price_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID do Preço na Stripe (price_...)"
    )
    stripe_product_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID do Produto na Stripe (prod_...)"
    )

    class Meta:
        verbose_name = "Preço do Plano"
        verbose_name_plural = "Preços dos Planos"
        unique_together = ('plan', 'currency', 'interval')
        ordering = ['currency', 'amount']

    def __str__(self):
        currency_symbol = 'R$' if self.currency == 'BRL' else ('$' if self.currency == 'USD' else '€')
        return f"{self.plan.name} - {currency_symbol} {self.amount} ({self.get_interval_display()})"


class Subscription(UUIDModel, TimeStampedModel):
    """Assinatura do usuário vinculada ao plano e ao cliente na Stripe."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name="Usuário"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name="Plano Atual"
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.BRL,
        verbose_name="Moeda da Assinatura"
    )
    interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        verbose_name="Ciclo Contratado"
    )
    stripe_customer_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="ID do Cliente Stripe (cus_...)"
    )
    stripe_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="ID da Assinatura Stripe (sub_...)"
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        verbose_name="Status"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Término do Ciclo Vigente"
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        verbose_name="Cancelar ao Término do Período"
    )

    class Meta:
        verbose_name = "Assinatura"
        verbose_name_plural = "Assinaturas"

    def __str__(self):
        return f"Assinatura de {self.user.email} - {self.plan.name} ({self.status})"

    @property
    def is_active(self):
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    @property
    def is_pro(self):
        return self.is_active and self.plan.is_pro


class PaymentTransaction(UUIDModel, TimeStampedModel):
    """Auditoria financeira de transações e webhooks de pagamento."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="Usuário"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Pago")
    currency = models.CharField(max_length=3, choices=Currency.choices, verbose_name="Moeda")
    stripe_invoice_id = models.CharField(max_length=100, blank=True, verbose_name="ID da Fatura Stripe")
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, verbose_name="ID do Payment Intent")
    status = models.CharField(max_length=50, default='succeeded', verbose_name="Status da Transação")

    class Meta:
        verbose_name = "Transação Financeira"
        verbose_name_plural = "Transações Financeiras"
        ordering = ['-created_at']

    def __str__(self):
        return f"Transação {self.currency} {self.amount} - {self.user.email} ({self.status})"
