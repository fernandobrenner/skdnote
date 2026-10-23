from .models import Note


def get_user_notes_quota(user):
    """
    Calcula a cota de notas ativas do usuário.
    Plano Gratuito: Limitado a 50 notas ativas.
    Plano Pro / Administrador: Notas ilimitadas.
    """
    if not user.is_authenticated:
        return {
            'is_pro': False,
            'current_notes': 0,
            'max_notes': 50,
            'can_create': False,
            'percentage': 0,
        }

    # Administradores têm acesso ilimitado
    if user.is_admin:
        current_notes = Note.objects.filter(user=user, is_deleted=False).count()
        return {
            'is_pro': True,
            'current_notes': current_notes,
            'max_notes': None,
            'can_create': True,
            'percentage': 0,
        }

    # Verifica se possui assinatura Pro ativa (vinculada em subscriptions)
    subscription = getattr(user, 'subscription', None)
    is_pro = subscription and subscription.is_active and (subscription.plan and subscription.plan.code == 'pro')

    current_notes = Note.objects.filter(user=user, is_deleted=False).count()

    if is_pro:
        return {
            'is_pro': True,
            'current_notes': current_notes,
            'max_notes': None,
            'can_create': True,
            'percentage': 0,
        }

    # Plano Gratuito (Starter): Até 50 notas
    max_notes = 50
    can_create = current_notes < max_notes
    percentage = min(100, int((current_notes / max_notes) * 100))

    return {
        'is_pro': False,
        'current_notes': current_notes,
        'max_notes': max_notes,
        'can_create': can_create,
        'percentage': percentage,
    }


def user_can_create_note(user) -> bool:
    """Verifica se o usuário pode criar uma nova nota ativa."""
    return get_user_notes_quota(user)['can_create']
