from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserType, Currency
from subscriptions.models import Plan, Subscription, SubscriptionStatus, PaymentTransaction
from subscriptions.services import ensure_default_plans
from core.models import SystemAnnouncement
from notes.models import Note


class CustomAdministrationPanelTests(TestCase):
    def setUp(self):
        self.client = Client()
        ensure_default_plans()

        # Usuário Administrador
        self.admin_user = User.objects.create_superuser(
            email='admin@skdnote.com',
            password='AdminPassword123!',
            full_name='Super Administrador'
        )

        # Usuário Cliente Padrão
        self.customer = User.objects.create_user(
            email='cliente.comum@exemplo.com',
            password='UserPassword123!',
            full_name='Cliente Comum',
            preferred_currency=Currency.BRL
        )

    def test_customer_cannot_access_admin_dashboard(self):
        """Verifica se cliente comum é bloqueado com status 403 ao tentar acessar o painel admin."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('administration:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_access_any_administration_routes(self):
        """Garante que cliente comum recebe HTTP 403 Forbidden em todos os endpoints administrativos."""
        self.client.force_login(self.customer)
        
        # Rotas GET
        self.assertEqual(self.client.get(reverse('administration:customers')).status_code, 403)
        self.assertEqual(self.client.get(reverse('administration:transactions')).status_code, 403)
        self.assertEqual(self.client.get(reverse('administration:announcements')).status_code, 403)

        # Rotas POST
        toggle_pro_url = reverse('administration:customer_toggle_pro', kwargs={'user_id': self.customer.id})
        self.assertEqual(self.client.post(toggle_pro_url).status_code, 403)

        toggle_status_url = reverse('administration:customer_toggle_status', kwargs={'user_id': self.customer.id})
        self.assertEqual(self.client.post(toggle_status_url).status_code, 403)

        announcement_create_url = reverse('administration:announcement_create')
        self.assertEqual(self.client.post(announcement_create_url, {'title': 'Hack', 'message': 'Fail'}).status_code, 403)

    def test_unauthenticated_user_redirected_to_login(self):
        """Verifica se visitante não-autenticado é redirecionado para a tela de login."""
        response = self.client.get(reverse('administration:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_can_access_dashboard_and_metrics(self):
        """Verifica se administrador acessa o painel com as métricas consolidadas."""
        self.client.force_login(self.admin_user)

        # Simula pagamentos
        PaymentTransaction.objects.create(user=self.customer, amount=Decimal('9.90'), currency='BRL', status='succeeded')
        PaymentTransaction.objects.create(user=self.customer, amount=Decimal('1.99'), currency='USD', status='succeeded')

        response = self.client.get(reverse('administration:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visão Geral do SaaS")
        self.assertContains(response, "R$ 9,90")
        self.assertContains(response, "$ 1,99")

    def test_hot_leads_detection_at_dashboard(self):
        """Verifica identificação de leads quentes (clientes gratuitos com mais de 35 notas)."""
        # Cria 40 notas para o cliente
        notes = [Note(user=self.customer, title=f"Nota Lead {i}") for i in range(40)]
        Note.objects.bulk_create(notes)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('administration:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cliente.comum@exemplo.com")
        self.assertContains(response, "<strong>40</strong> / 50 notas")

    def test_admin_can_toggle_pro_plan_for_customer(self):
        """Verifica concessão e revogação manual de Plano Pro VIP para clientes."""
        self.client.force_login(self.admin_user)

        # Concede Pro
        response = self.client.post(reverse('administration:customer_toggle_pro', kwargs={'user_id': self.customer.id}))
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.subscription.is_pro)

        # Revoga Pro
        self.client.post(reverse('administration:customer_toggle_pro', kwargs={'user_id': self.customer.id}))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.subscription.is_pro)

    def test_admin_can_suspend_and_reactivate_customer(self):
        """Verifica suspensão e reativação de conta de cliente."""
        self.client.force_login(self.admin_user)

        # Suspende
        self.client.post(reverse('administration:customer_toggle_status', kwargs={'user_id': self.customer.id}))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

        # Reativa
        self.client.post(reverse('administration:customer_toggle_status', kwargs={'user_id': self.customer.id}))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_admin_can_create_and_toggle_system_announcement(self):
        """Verifica publicação e controle de avisos globais do sistema."""
        self.client.force_login(self.admin_user)

        # Cria comunicado
        self.client.post(reverse('administration:announcement_create'), {
            'title': 'Manutenção de Servidores',
            'message': 'O sistema passará por melhorias na madrugada.',
            'level': 'WARNING',
        })
        self.assertTrue(SystemAnnouncement.objects.filter(title='Manutenção de Servidores').exists())
        announcement = SystemAnnouncement.objects.get(title='Manutenção de Servidores')
        self.assertTrue(announcement.is_active)

        # Alterna para inativo
        self.client.post(reverse('administration:announcement_toggle', kwargs={'announcement_id': announcement.id}))
        announcement.refresh_from_db()
        self.assertFalse(announcement.is_active)
