import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Currency
from subscriptions.models import Plan, PlanPrice, Subscription, SubscriptionStatus, BillingInterval, PaymentTransaction
from subscriptions.services import ensure_default_plans, activate_user_pro_subscription
from notes.models import Note
from notes.services import get_user_notes_quota, user_can_create_note


class StripeMultiCurrencyBillingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='assinante@exemplo.com',
            password='Password123!',
            full_name='Assinante Pro',
            preferred_currency=Currency.BRL
        )
        self.client.force_login(self.user)
        self.free_plan, self.pro_plan = ensure_default_plans()

    def test_ensure_default_plans_and_multi_currency_prices(self):
        """Verifica a criação dos planos padrão e das tabelas de preços em BRL, USD e EUR."""
        self.assertTrue(Plan.objects.filter(code='free').exists())
        self.assertTrue(Plan.objects.filter(code='pro').exists())

        # Verifica existência de preços para BRL, USD e EUR
        for curr in [Currency.BRL, Currency.USD, Currency.EUR]:
            prices = PlanPrice.objects.filter(plan=self.pro_plan, currency=curr)
            self.assertEqual(prices.count(), 3)  # Mensal, Anual e Vitalício

    def test_pricing_view_multi_currency(self):
        """Verifica se a página de planos responde com status 200 para BRL, USD e EUR."""
        for curr in ['BRL', 'USD', 'EUR']:
            response = self.client.get(reverse('subscriptions:pricing') + f'?currency={curr}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(curr, response.content.decode())

    def test_checkout_and_pro_activation_unlocks_unlimited_notes(self):
        """Verifica se a ativação do Pro desbloqueia a criação de mais de 50 notas."""
        # Cria 50 notas no plano gratuito
        notes = [Note(user=self.user, title=f"Nota {i}") for i in range(50)]
        Note.objects.bulk_create(notes)

        quota_before = get_user_notes_quota(self.user)
        self.assertFalse(quota_before['can_create'])

        # Preço Pro Mensal em BRL
        price_brl = PlanPrice.objects.get(plan=self.pro_plan, currency=Currency.BRL, interval=BillingInterval.MONTHLY)

        # Simula sucesso do checkout
        response = self.client.get(reverse('subscriptions:checkout_success') + f'?mock_price_id={price_brl.id}')
        self.assertEqual(response.status_code, 200)

        # Verifica se o usuário agora tem Pro ativo
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, 'subscription'))
        self.assertTrue(self.user.subscription.is_pro)

        # Verifica se agora pode criar mais de 50 notas sem bloqueio
        quota_after = get_user_notes_quota(self.user)
        self.assertTrue(quota_after['is_pro'])
        self.assertIsNone(quota_after['max_notes'])
        self.assertTrue(quota_after['can_create'])
        self.assertTrue(user_can_create_note(self.user))

        # Cria a 51ª nota com sucesso
        response_51 = self.client.post(reverse('notes:note_create'))
        self.assertEqual(response_51.status_code, 302)
        self.assertEqual(Note.objects.filter(user=self.user).count(), 51)

    def test_stripe_webhook_checkout_completed(self):
        """Verifica se o webhook 'checkout.session.completed' ativa o Pro e registra a transação."""
        price_usd = PlanPrice.objects.get(plan=self.pro_plan, currency=Currency.USD, interval=BillingInterval.YEARLY)

        webhook_payload = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'client_reference_id': str(self.user.id),
                    'customer': 'cus_stripe_test_123',
                    'subscription': 'sub_stripe_test_456',
                    'metadata': {
                        'plan_price_id': str(price_usd.id)
                    }
                }
            }
        }

        response = self.client.post(
            reverse('subscriptions:stripe_webhook'),
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Verifica assinatura ativada
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'pro')
        self.assertEqual(sub.stripe_customer_id, 'cus_stripe_test_123')
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

        # Verifica transação auditada
        self.assertTrue(PaymentTransaction.objects.filter(user=self.user, amount=price_usd.amount).exists())

    def test_stripe_webhook_subscription_deleted(self):
        """Verifica se o webhook 'customer.subscription.deleted' rebaixa para o plano gratuito."""
        price_eur = PlanPrice.objects.get(plan=self.pro_plan, currency=Currency.EUR, interval=BillingInterval.MONTHLY)
        activate_user_pro_subscription(self.user, price_eur, stripe_customer_id="cus_eur", stripe_sub_id="sub_eur_cancel")

        webhook_cancel = {
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': 'sub_eur_cancel'
                }
            }
        }

        response = self.client.post(
            reverse('subscriptions:stripe_webhook'),
            data=json.dumps(webhook_cancel),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')
        self.assertEqual(sub.status, SubscriptionStatus.CANCELED)
