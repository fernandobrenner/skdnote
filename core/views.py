import os
from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect


def home(request):
    """Página inicial com apresentação do produto ou redirecionamento se autenticado."""
    if request.user.is_authenticated:
        return redirect('notes:app')
    return render(request, 'core/landing.html')


def robots_txt_view(request):
    """Serve o arquivo robots.txt diretamente para buscadores."""
    robots_path = os.path.join(settings.BASE_DIR, 'static', 'robots.txt')
    if os.path.exists(robots_path):
        with open(robots_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='text/plain')
    return HttpResponse("User-agent: *\nAllow: /\n", content_type='text/plain')


def sitemap_xml_view(request):
    """Serve o sitemap.xml para indexação por mecanismos de busca."""
    sitemap_path = os.path.join(settings.BASE_DIR, 'static', 'sitemap.xml')
    if os.path.exists(sitemap_path):
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='application/xml')
    raise Http404("Sitemap não encontrado")


def service_worker_view(request):
    """Serve o service worker (sw.js) na raiz com o cabeçalho correto de escopo."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            response = HttpResponse(f.read(), content_type='application/javascript; charset=utf-8')
            response['Service-Worker-Allowed'] = '/'
            return response
    raise Http404("Service Worker não encontrado")


def offline_view(request):
    """Página de contingência offline do PWA."""
    return render(request, 'pwa/offline.html')


def privacy_policy_view(request):
    """Página de Política de Privacidade e LGPD."""
    return render(request, 'legal/privacy_policy.html')


def terms_of_service_view(request):
    """Página de Termos de Uso do Serviço."""
    return render(request, 'legal/terms_of_service.html')


def cookie_policy_view(request):
    """Página de Política de Cookies."""
    return render(request, 'legal/cookie_policy.html')


def data_request_view(request):
    """Portal de Direitos do Titular LGPD (Art. 18)."""
    return render(request, 'legal/data_request.html')


def custom_page_not_found_view(request, exception=None):
    """Handler customizado para Erro 404."""
    return render(request, '404.html', status=404)


def custom_server_error_view(request):
    """Handler customizado para Erro 500."""
    return render(request, '500.html', status=500)


def custom_permission_denied_view(request, exception=None):
    """Handler customizado para Erro 403."""
    return render(request, '403.html', status=403)
