from django.urls import path
from .views import (
    login_view,
    logout_view,
    register_view,
    password_reset_view,
    password_reset_done_view,
    password_reset_confirm_view,
    password_reset_complete_view,
    password_change_view,
    password_change_done_view,
    lgpd_export_data_view,
    lgpd_delete_account_view,
    lgpd_consent_api_view,
)

urlpatterns = [
    # Cadastro e Login (Function-Based Views)
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Fluxo de Redefinição de Senha (Function-Based Views)
    path('password-reset/', password_reset_view, name='password_reset'),
    path('password-reset/done/', password_reset_done_view, name='password_reset_done'),
    path('reset/<uidb64>/<token>/', password_reset_confirm_view, name='password_reset_confirm'),
    path('reset/done/', password_reset_complete_view, name='password_reset_complete'),

    # Alteração de Senha do Usuário Logado (Function-Based Views)
    path('password-change/', password_change_view, name='password_change'),
    path('password-change/done/', password_change_done_view, name='password_change_done'),

    # Conformidade LGPD (Direitos do Titular — Art. 18)
    path('lgpd/export-data/', lgpd_export_data_view, name='lgpd_export_data'),
    path('lgpd/delete-account/', lgpd_delete_account_view, name='lgpd_delete_account'),
    path('api/lgpd-consent/', lgpd_consent_api_view, name='lgpd_consent_api'),
]
