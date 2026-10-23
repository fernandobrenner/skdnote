from functools import wraps
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """
    Decorator que restringe o acesso estritamente a usuários administradores (role='ADMIN' ou is_superuser).
    Caso não esteja logado, redireciona para o login com ?next=.
    Caso esteja logado mas seja cliente (CUSTOMER), gera PermissionDenied (HTTP 403).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if not request.user.is_admin:
            raise PermissionDenied("Acesso restrito a administradores.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
