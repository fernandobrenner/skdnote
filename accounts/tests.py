from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from accounts.models import User, UserType, Currency, ConsentLog


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='cliente@exemplo.com',
            password='Password123!',
            full_name='Cliente Teste',
            preferred_currency=Currency.BRL
        )

    def test_user_creation_and_attributes(self):
        """Verifica se o CustomUser é criado com email como identificador e tipo CUSTOMER."""
        self.assertEqual(self.user.email, 'cliente@exemplo.com')
        self.assertEqual(self.user.role, UserType.CUSTOMER)
        self.assertTrue(self.user.is_customer)
        self.assertFalse(self.user.is_admin)

    def test_login_with_email(self):
        """Verifica se o login funciona com email e senha."""
        response = self.client.post(reverse('login'), {
            'username': 'cliente@exemplo.com',
            'password': 'Password123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('notes:app'))

    def test_registration_creates_user_and_consent_log(self):
        """Verifica se o cadastro cria o cliente e grava o ConsentLog da LGPD."""
        response = self.client.post(reverse('register'), {
            'full_name': 'Novo Cliente',
            'email': 'novo@exemplo.com',
            'preferred_currency': 'BRL',
            'password': 'SafePassword88!',
            'password_confirm': 'SafePassword88!',
            'accept_terms': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='novo@exemplo.com').exists())
        novo_user = User.objects.get(email='novo@exemplo.com')
        self.assertTrue(ConsentLog.objects.filter(user=novo_user).exists())

    def test_password_reset_flow(self):
        """Verifica se o formulário de redefinição de senha dispara o e-mail de recuperação."""
        response = self.client.post(reverse('password_reset'), {
            'email': 'cliente@exemplo.com'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Redefinição de senha no skdnote', mail.outbox[0].subject)
