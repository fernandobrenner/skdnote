from django.urls import path, include
from core.views import (
    home,
    robots_txt_view,
    sitemap_xml_view,
    service_worker_view,
    offline_view,
    privacy_policy_view,
    terms_of_service_view,
    cookie_policy_view,
    data_request_view,
    custom_page_not_found_view,
    custom_server_error_view,
    custom_permission_denied_view,
)
from accounts.views import login_view, logout_view, register_view
from subscriptions.views import pricing_view
from notes.views import shared_note_view

urlpatterns = [
    # Página Inicial / Marketing
    path('', home, name='home'),

    # Service Worker PWA
    path('sw.js', service_worker_view, name='service_worker'),

    # Link Público de Anotação Compartilhada
    path('share/<str:share_token>/', shared_note_view, name='shared_note_root'),

    # SEO & Indexação (robots.txt e sitemap.xml)
    path('robots.txt', robots_txt_view, name='robots_txt'),
    path('sitemap.xml', sitemap_xml_view, name='sitemap_xml'),

    # PWA Offline Fallback
    path('offline/', offline_view, name='offline'),

    # Páginas Legais e LGPD
    path('politica-de-privacidade/', privacy_policy_view, name='privacy_policy'),
    path('termos-de-uso/', terms_of_service_view, name='terms_of_service'),
    path('cookies/', cookie_policy_view, name='cookie_policy'),
    path('dados-pessoais/', data_request_view, name='data_request'),

    # Atalhos diretos de autenticação (Function-Based Views)
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    # Rotas completas de contas, redefinição de senha e LGPD
    path('accounts/', include('accounts.urls')),

    # Módulo de Assinaturas e Stripe Multi-Moeda
    path('subscriptions/', include('subscriptions.urls')),
    path('planos/', pricing_view, name='pricing_shortcut'),


    # Aplicativo de Anotações (Área do Cliente)
    path('app/', include('notes.urls')),

    # Módulo de Exportações e Backup
    path('exports/', include('exports.urls')),

    # Painel Administrativo Customizado (Substitui django-admin)
    path('manage/', include('administration.urls')),
]


# Handlers globais de erro HTTP (Function-Based Views)
handler404 = 'core.views.custom_page_not_found_view'
handler500 = 'core.views.custom_server_error_view'
handler403 = 'core.views.custom_permission_denied_view'
