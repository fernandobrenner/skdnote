from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Currency


class SEOPWAandLGPDTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='titular@exemplo.com',
            password='Password123!',
            full_name='Titular de Dados',
            preferred_currency=Currency.BRL
        )

    def test_robots_txt_status_and_content_type(self):
        """Verifica se /robots.txt responde com status 200 e content_type text/plain."""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertIn('User-agent', response.content.decode())

    def test_sitemap_xml_status_and_content_type(self):
        """Verifica se /sitemap.xml responde com status 200 e content_type application/xml."""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
        self.assertIn('<urlset', response.content.decode())

    def test_pwa_offline_page(self):
        """Verifica se a rota de contingência offline /offline/ responde com status 200."""
        response = self.client.get('/offline/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('offline', response.content.decode().lower())

    def test_legal_pages_status(self):
        """Verifica se as páginas legais (Privacidade, Termos e Cookies) respondem com 200."""
        for url in ['/politica-de-privacidade/', '/termos-de-uso/', '/cookies/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Falha na rota {url}")

    def test_lgpd_export_requires_auth(self):
        """Verifica se a exportação de dados requer login e redireciona visitante não-autenticado."""
        response = self.client.get('/accounts/lgpd/export-data/')
        self.assertEqual(response.status_code, 302)

    def test_lgpd_export_data_json_for_authenticated_user(self):
        """Verifica se o titular de dados consegue exportar seus dados em formato JSON."""
        self.client.force_login(self.user)
        response = self.client.get('/accounts/lgpd/export-data/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])
        data = response.json()
        self.assertEqual(data['user_profile']['email'], 'titular@exemplo.com')
        self.assertEqual(data['platform'], 'skdnote')


class GeolocationAndGeoPricingTests(TestCase):
    def setUp(self):
        from django.test import RequestFactory
        from subscriptions.services import ensure_default_plans
        self.factory = RequestFactory()
        self.client = Client()
        ensure_default_plans()

    def test_detect_country_from_cf_header(self):
        """Verifica detecção de país via cabeçalho Cloudflare (CF-IPCountry)."""
        from core.geolocation import detect_country_from_request, map_country_to_currency
        request = self.factory.get('/planos/', HTTP_CF_IPCOUNTRY='BR')
        self.assertEqual(detect_country_from_request(request), 'BR')
        self.assertEqual(map_country_to_currency('BR'), Currency.BRL)

        request_pt = self.factory.get('/planos/', HTTP_CF_IPCOUNTRY='PT')
        self.assertEqual(detect_country_from_request(request_pt), 'PT')
        self.assertEqual(map_country_to_currency('PT'), Currency.EUR)

        request_us = self.factory.get('/planos/', HTTP_CF_IPCOUNTRY='US')
        self.assertEqual(detect_country_from_request(request_us), 'US')
        self.assertEqual(map_country_to_currency('US'), Currency.USD)

    def test_map_eurozone_countries_to_eur(self):
        """Verifica se diversos países da zona do euro são mapeados para EUR."""
        from core.geolocation import map_country_to_currency
        for euro_country in ['DE', 'FR', 'ES', 'IT', 'NL', 'IE']:
            self.assertEqual(map_country_to_currency(euro_country), Currency.EUR)

    def test_pricing_page_auto_detected_currency_from_geolocation(self):
        """Verifica se a página de preços exibe a moeda correspondente à geolocalização do cliente."""
        # 1. Cliente da Europa (Alemanha)
        response_eu = self.client.get('/planos/', HTTP_CF_IPCOUNTRY='DE')
        self.assertEqual(response_eu.status_code, 200)
        self.assertContains(response_eu, 'EUR')
        self.assertContains(response_eu, 'DE')

        # 2. Cliente do Brasil
        response_br = self.client.get('/planos/', HTTP_CF_IPCOUNTRY='BR')
        self.assertEqual(response_br.status_code, 200)
        self.assertContains(response_br, 'BRL')
        self.assertContains(response_br, 'BR')

        # 3. Cliente dos EUA ou Internacional
        response_us = self.client.get('/planos/', HTTP_CF_IPCOUNTRY='US')
        self.assertEqual(response_us.status_code, 200)
        self.assertContains(response_us, 'USD')
        self.assertContains(response_us, 'US')

    def test_manual_currency_override_overrules_geolocation(self):
        """Verifica se a seleção manual de moeda pelo usuário sobrepõe a geolocalização."""
        response = self.client.get('/planos/?currency=USD', HTTP_CF_IPCOUNTRY='BR')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_currency'], 'USD')
