import ipaddress
import urllib.request
from accounts.models import Currency

# Países membros da Zona do Euro (utilizam EUR)
EUROZONE_COUNTRIES = {
    'AT', 'BE', 'CY', 'EE', 'FI', 'FR', 'DE', 'GR', 'IE', 'IT',
    'LV', 'LT', 'LU', 'MT', 'NL', 'PT', 'SK', 'SI', 'ES', 'HR'
}

CURRENCY_SYMBOLS = {
    'BRL': 'R$',
    'USD': '$',
    'EUR': '€',
}

CURRENCY_FLAGS = {
    'BRL': '🇧🇷',
    'USD': '🇺🇸',
    'EUR': '🇪🇺',
}


def is_private_or_local_ip(ip_str: str) -> bool:
    """Verifica se o IP é de loopback ou rede privada interna."""
    if not ip_str:
        return True
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return True


def get_client_ip(request) -> str:
    """Obtém o IP real do cliente considerando cabeçalhos de proxies reversos (ex: Cloudflare, Nginx)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
        if ip:
            return ip
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def detect_country_from_request(request) -> str:
    """
    Detecta o código de país ISO de 2 letras (ex: 'BR', 'US', 'PT', 'DE') a partir da requisição.
    Ordem de prioridade:
    1. Cabeçalhos de CDN / Reverse Proxy de produção (Cloudflare, AWS CloudFront, etc.)
    2. Cache de sessão do usuário
    3. Consulta de IP (para IPs públicos reais)
    4. Heurística inteligente baseada no Accept-Language do navegador
    """
    # 1. Cabeçalhos diretos de CDN em produção (0ms de latência e 100% confiável)
    cdn_country = (
        request.META.get('HTTP_CF_IPCOUNTRY') or
        request.META.get('HTTP_CLOUDFRONT_VIEWER_COUNTRY') or
        request.META.get('HTTP_X_COUNTRY_CODE') or
        request.META.get('HTTP_GEOIP_COUNTRY_CODE')
    )
    if cdn_country and cdn_country.strip() and cdn_country.upper() != 'XX':
        country_code = cdn_country.strip().upper()
        if hasattr(request, 'session'):
            request.session['geo_country_code'] = country_code
        return country_code

    # 2. Sessão salva previamente
    if hasattr(request, 'session'):
        session_country = request.session.get('geo_country_code')
        if session_country:
            return session_country

    # 3. Consulta de IP para IPs públicos
    client_ip = get_client_ip(request)
    if not is_private_or_local_ip(client_ip):
        try:
            req = urllib.request.Request(
                f"https://ipapi.co/{client_ip}/country/",
                headers={'User-Agent': 'skdnote-geo/1.0'}
            )
            with urllib.request.urlopen(req, timeout=1.2) as response:
                result = response.read().decode('utf-8').strip().upper()
                if len(result) == 2 and result.isalpha():
                    if hasattr(request, 'session'):
                        request.session['geo_country_code'] = result
                    return result
        except Exception:
            pass

    # 4. Heurística inteligente baseada no cabeçalho Accept-Language do navegador
    accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '').lower()
    if 'pt-br' in accept_lang:
        country_code = 'BR'
    elif any(lang in accept_lang for lang in ['pt-pt', 'pt', 'es-', 'fr-', 'de-', 'it-', 'nl-']):
        country_code = 'PT'
    elif 'en-' in accept_lang or 'en' in accept_lang:
        country_code = 'US'
    else:
        country_code = 'BR'

    if hasattr(request, 'session'):
        request.session['geo_country_code'] = country_code
    return country_code


def map_country_to_currency(country_code: str) -> str:
    """Mapeia o código de país ISO para a moeda suportada no Stripe (BRL, EUR, USD)."""
    if not country_code:
        return Currency.BRL

    code = country_code.upper()
    if code == 'BR':
        return Currency.BRL
    elif code in EUROZONE_COUNTRIES:
        return Currency.EUR
    else:
        # Estados Unidos e demais países internacionais
        return Currency.USD


def get_client_currency(request) -> str:
    """
    Retorna a moeda recomendada para o cliente com suporte a override manual.
    Ordem de resolução:
    1. Parâmetro explícito na URL (?currency=...)
    2. Override manual salvo na sessão
    3. Preferência de conta do usuário logado (se houver)
    4. Geolocalização automática do cliente
    """
    # 1. Parâmetro GET
    url_currency = request.GET.get('currency', '').upper()
    if url_currency in [Currency.BRL, Currency.USD, Currency.EUR]:
        if hasattr(request, 'session'):
            request.session['currency_override'] = url_currency
        return url_currency

    # 2. Sessão com escolha manual prévia
    if hasattr(request, 'session'):
        session_override = request.session.get('currency_override')
        if session_override in [Currency.BRL, Currency.USD, Currency.EUR]:
            return session_override

    # 3. Usuário autenticado com moeda cadastrada
    if hasattr(request, 'user') and request.user.is_authenticated and request.user.preferred_currency:
        return request.user.preferred_currency

    # 4. Detecção automática por Geolocalização
    country_code = detect_country_from_request(request)
    return map_country_to_currency(country_code)


def get_currency_display_info(currency_code: str) -> dict:
    """Retorna símbolo e bandeira para exibição da moeda."""
    curr = currency_code or Currency.BRL
    return {
        'code': curr,
        'symbol': CURRENCY_SYMBOLS.get(curr, 'R$'),
        'flag': CURRENCY_FLAGS.get(curr, '🇧🇷'),
    }
