from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    get_user_model,
    update_session_auth_hash,
)
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode

from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    CustomPasswordChangeForm,
)
from .models import ConsentLog
from core.geolocation import get_client_currency

UserModel = get_user_model()


def login_view(request):
    """View em formato de função para login com suporte a e-mail e lembrar sessão."""
    if request.user.is_authenticated:
        if request.user.is_admin:
            return redirect('administration:dashboard')
        return redirect('notes:app')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            
            remember_me = form.cleaned_data.get('remember_me')
            if not remember_me:
                # Expira ao fechar navegador
                request.session.set_expiry(0)
            else:
                # Sessão mantida por 30 dias
                request.session.set_expiry(30 * 24 * 60 * 60)

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if user.is_admin:
                return redirect('administration:dashboard')
            return redirect('notes:app')
    else:
        form = CustomAuthenticationForm(request)

    return render(request, 'registration/login.html', {'form': form})


def register_view(request):
    """View em formato de função para cadastro de novos clientes com registro LGPD."""
    if request.user.is_authenticated:
        return redirect('notes:app')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Captura de dados de auditoria LGPD
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

            ConsentLog.objects.create(
                user=user,
                ip_address=ip,
                user_agent=user_agent,
                terms_version="1.0",
                privacy_policy_version="1.0",
                accepted_cookies_essential=True,
                accepted_cookies_analytics=True,
            )

            # Efetua login automático do novo cliente
            auth_login(request, user)
            return redirect('notes:app')
    else:
        form = CustomUserCreationForm(initial={
            'preferred_currency': get_client_currency(request)
        })

    return render(request, 'registration/register.html', {'form': form})


def logout_view(request):
    """View em formato de função para encerramento de sessão."""
    auth_logout(request)
    return render(request, 'registration/logged_out.html')


def password_reset_view(request):
    """View em formato de função para solicitação de redefinição de senha."""
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name='registration/password_reset_email.html',
                subject_template_name='registration/password_reset_subject.txt',
            )
            return redirect('password_reset_done')
    else:
        form = CustomPasswordResetForm()

    return render(request, 'registration/password_reset_form.html', {'form': form})


def password_reset_done_view(request):
    """View em formato de função para confirmação de e-mail enviado."""
    return render(request, 'registration/password_reset_done.html')


def password_reset_confirm_view(request, uidb64, token):
    """View em formato de função para validação do token e definição da nova senha."""
    user = None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = UserModel._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist, ValidationError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        validlink = True
        if request.method == 'POST':
            form = CustomSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                return redirect('password_reset_complete')
        else:
            form = CustomSetPasswordForm(user)
    else:
        validlink = False
        form = None

    return render(request, 'registration/password_reset_confirm.html', {
        'form': form,
        'validlink': validlink,
    })


def password_reset_complete_view(request):
    """View em formato de função para conclusão de redefinição de senha."""
    return render(request, 'registration/password_reset_complete.html')


@login_required
def password_change_view(request):
    """View em formato de função para alteração de senha de usuário autenticado."""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            return redirect('password_change_done')
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'registration/password_change_form.html', {'form': form})


@login_required
def password_change_done_view(request):
    """View em formato de função para confirmação de alteração de senha."""
    return render(request, 'registration/password_change_done.html')


import json
from django.http import HttpResponse, JsonResponse


@login_required
def lgpd_export_data_view(request):
    """Direito de Acesso e Portabilidade (Art. 18 LGPD): Exporta todos os dados do titular em JSON."""
    user = request.user
    consent_logs = [
        {
            'accepted_at': log.created_at.isoformat(),
            'ip_address': log.ip_address,
            'terms_version': log.terms_version,
            'privacy_policy_version': log.privacy_policy_version,
            'accepted_cookies_essential': log.accepted_cookies_essential,
            'accepted_cookies_analytics': log.accepted_cookies_analytics,
        }
        for log in user.consent_logs.all()
    ]

    export_payload = {
        'platform': 'skdnote',
        'exported_at': user.updated_at.isoformat(),
        'user_profile': {
            'id': str(user.id),
            'email': user.email,
            'full_name': user.full_name,
            'role': user.get_role_display(),
            'preferred_currency': user.preferred_currency,
            'theme': user.theme,
            'editor_font': user.editor_font,
            'created_at': user.created_at.isoformat(),
        },
        'lgpd_consent_history': consent_logs,
        'notes_data': [],  # Populado na Fase 3 com as notas do usuário
    }

    response = HttpResponse(
        json.dumps(export_payload, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="skdnote-dados-pessoais-{user.id}.json"'
    return response


@login_required
def lgpd_delete_account_view(request):
    """Direito à Eliminação / Esquecimento (Art. 18, VI LGPD): Exclui irreversivelmente a conta e dados."""
    if request.method == 'POST':
        user = request.user
        auth_logout(request)
        user.delete()
        return redirect('home')
    return redirect('data_request')


def lgpd_consent_api_view(request):
    """API assíncrona para gravação de consentimento de cookies da LGPD."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            if request.user.is_authenticated:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
                
                ConsentLog.objects.create(
                    user=request.user,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    terms_version="1.0",
                    privacy_policy_version="1.0",
                    accepted_cookies_essential=data.get('essential', True),
                    accepted_cookies_analytics=data.get('analytics', False),
                    accepted_cookies_marketing=data.get('marketing', False),
                )
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid_method'}, status=405)

