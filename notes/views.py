import json
import re
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from .models import Note, Notebook, Tag
from .services import get_user_notes_quota, user_can_create_note


@login_required
def app_view(request):
    """
    Interface principal do skdnote (estilo UpNote):
    Navegação hierárquica à esquerda, lista de notas no centro e editor à direita.
    """
    user = request.user
    quota = get_user_notes_quota(user)

    current_filter = request.GET.get('filter', 'all')
    notebook_id = request.GET.get('notebook')
    tag_id = request.GET.get('tag')
    search_query = request.GET.get('q', '').strip()
    selected_note_id = request.GET.get('note_id')

    # Base queryset para as notas do usuário
    notes_qs = Note.objects.filter(user=user)

    # Filtragem por estado / pasta
    active_notebook = None
    active_tag = None

    if current_filter == 'trash':
        notes_qs = notes_qs.filter(is_deleted=True)
    else:
        notes_qs = notes_qs.filter(is_deleted=False)

        if current_filter == 'pinned':
            notes_qs = notes_qs.filter(is_pinned=True)
        elif current_filter == 'favorites':
            notes_qs = notes_qs.filter(is_favorite=True)

        if notebook_id:
            active_notebook = get_object_or_404(Notebook, id=notebook_id, user=user)
            # Inclui notas do caderno e de subcadernos
            sub_ids = list(active_notebook.subnotebooks.values_list('id', flat=True))
            notes_qs = notes_qs.filter(Q(notebook=active_notebook) | Q(notebook_id__in=sub_ids))

        if tag_id:
            active_tag = get_object_or_404(Tag, id=tag_id, user=user)
            notes_qs = notes_qs.filter(tags=active_tag)

    # Busca em tempo real por título ou conteúdo
    if search_query:
        notes_qs = notes_qs.filter(
            Q(title__icontains=search_query) | Q(content_plain__icontains=search_query)
        )

    notes = list(notes_qs.select_related('notebook').prefetch_related('tags'))

    # Identifica a nota selecionada para exibição no editor
    selected_note = None
    if selected_note_id:
        selected_note = Note.objects.filter(id=selected_note_id, user=user).first()
    elif notes:
        selected_note = notes[0]

    # Cadernos raiz (com subcadernos pré-carregados) e Tags
    notebooks = Notebook.objects.filter(user=user, parent__isnull=True).prefetch_related('subnotebooks')
    tags = Tag.objects.filter(user=user)

    context = {
        'user': user,
        'quota': quota,
        'notebooks': notebooks,
        'tags': tags,
        'notes': notes,
        'selected_note': selected_note,
        'current_filter': current_filter,
        'active_notebook': active_notebook,
        'active_tag': active_tag,
        'search_query': search_query,
    }
    return render(request, 'notes/app.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def note_create_view(request):
    """
    Criação de nova nota com validação estrita do limitador de 50 notas no plano gratuito.
    """
    user = request.user
    quota = get_user_notes_quota(user)

    if not quota['can_create']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'quota_exceeded',
                'message': 'Você atingiu o limite de 50 notas do plano gratuito.',
                'quota': quota,
            }, status=402)
        return redirect(reverse('notes:app') + '?paywall=1')

    notebook_id = request.POST.get('notebook_id') or request.GET.get('notebook_id')
    notebook = None
    if notebook_id:
        notebook = Notebook.objects.filter(id=notebook_id, user=user).first()

    note = Note.objects.create(
        user=user,
        title="Sem título",
        notebook=notebook,
        content_plain="",
        content_html=""
    )

    tag_id = request.POST.get('tag_id') or request.GET.get('tag_id')
    if tag_id:
        tag = Tag.objects.filter(id=tag_id, user=user).first()
        if tag:
            note.tags.add(tag)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'status': 'ok',
            'note_id': str(note.id),
            'title': note.title,
            'redirect_url': f"{reverse('notes:app')}?note_id={note.id}"
        })

    return redirect(f"{reverse('notes:app')}?note_id={note.id}")


@login_required
@require_http_methods(['POST', 'PATCH'])
def note_autosave_view(request, note_id):
    """
    Endpoint rápido de autosave com debounce (500ms):
    Atualiza título, HTML e texto puro da anotação em segundo plano.
    """
    note = get_object_or_404(Note, id=note_id, user=request.user)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        title = data.get('title', '').strip()
        content_html = data.get('content_html', '')
        content_plain = data.get('content_plain', '').strip()

        # Se o título estiver vazio, infere a partir da 1ª linha de texto
        if not title and content_plain:
            first_line = content_plain.split('\n')[0].strip()
            title = first_line[:60] if first_line else "Sem título"
        elif not title:
            title = "Sem título"

        note.title = title
        note.content_html = content_html
        note.content_plain = content_plain

        if 'content_json' in data:
            note.content_json = data['content_json']

        note.save(update_fields=['title', 'content_html', 'content_plain', 'content_json', 'updated_at'])

        # Detecção e sincronização automática de hashtags (#tag) estilo UpNote
        raw_tags = re.findall(r'(?<![&a-zA-Z0-9#])#([a-zA-Z0-9_\u00C0-\u017F]{2,30})\b', f"{title} {content_plain}")
        for t_name in raw_tags:
            t_name = t_name.strip().lower()
            if re.match(r'^[0-9a-f]{3}$|^[0-9a-f]{6}$', t_name):
                continue
            tag, _ = Tag.objects.get_or_create(user=request.user, name=t_name)
            note.tags.add(tag)

        return JsonResponse({
            'status': 'saved',
            'note_id': str(note.id),
            'title': note.title,
            'preview': note.preview_text(),
            'updated_at': note.updated_at.strftime('%H:%M:%S'),
            'tags': [{'id': str(t.id), 'name': t.name, 'color': t.color} for t in note.tags.all()],
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def note_toggle_pin_view(request, note_id):
    """Alterna o status de fixada no topo da nota."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save(update_fields=['is_pinned', 'updated_at'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'is_pinned': note.is_pinned})
    return redirect(f"{reverse('notes:app')}?note_id={note.id}")


@login_required
@require_POST
def note_toggle_favorite_view(request, note_id):
    """Alterna o status de favorita da nota."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.is_favorite = not note.is_favorite
    note.save(update_fields=['is_favorite', 'updated_at'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'is_favorite': note.is_favorite})
    return redirect(f"{reverse('notes:app')}?note_id={note.id}")


@login_required
@require_POST
def note_move_to_trash_view(request, note_id):
    """Move a anotação para a lixeira (soft delete)."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.move_to_trash()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'trashed', 'note_id': str(note.id)})
    return redirect('notes:app')


@login_required
@require_POST
def note_restore_view(request, note_id):
    """Restaura a anotação da lixeira."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.restore_from_trash()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'restored', 'note_id': str(note.id)})
    return redirect(f"{reverse('notes:app')}?note_id={note.id}")


@login_required
@require_POST
def note_delete_permanent_view(request, note_id):
    """Exclui permanentemente a anotação que está na lixeira."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'deleted_permanently'})
    return redirect(reverse('notes:app') + '?filter=trash')


@login_required
@require_POST
def notebook_create_view(request):
    """Criação de novo caderno ou subcaderno."""
    title = request.POST.get('title', '').strip()
    if not title:
        return HttpResponseBadRequest("Título é obrigatório.")

    icon = request.POST.get('icon', '📁').strip()
    color = request.POST.get('color', '#6366f1').strip()
    parent_id = request.POST.get('parent_id')

    parent = None
    if parent_id:
        parent = Notebook.objects.filter(id=parent_id, user=request.user).first()

    notebook = Notebook.objects.create(
        user=request.user,
        title=title,
        icon=icon,
        color=color,
        parent=parent
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'notebook_id': str(notebook.id),
            'title': notebook.title
        })
    return redirect(reverse('notes:app') + f'?notebook={notebook.id}')


@login_required
@require_POST
def notebook_delete_view(request, notebook_id):
    """Exclusão de caderno."""
    notebook = get_object_or_404(Notebook, id=notebook_id, user=request.user)
    notebook.delete()
    return redirect('notes:app')


@login_required
@require_POST
def tag_create_view(request):
    """Criação de nova etiqueta."""
    name = request.POST.get('name', '').strip().replace('#', '')
    if not name:
        return HttpResponseBadRequest("Nome da tag é obrigatório.")

    color = request.POST.get('color', '#818cf8').strip()
    tag, _ = Tag.objects.get_or_create(user=request.user, name=name, defaults={'color': color})

    note_id = request.POST.get('note_id')
    if note_id:
        note = Note.objects.filter(id=note_id, user=request.user).first()
        if note:
            note.tags.add(tag)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'tag_id': str(tag.id), 'name': tag.name, 'color': tag.color})
    return redirect(reverse('notes:app') + f'?tag={tag.id}')


@login_required
@require_POST
def note_tag_toggle_view(request, note_id):
    """
    Associa ou desassocia uma etiqueta de uma anotação (UpNote tag toggle).
    """
    note = get_object_or_404(Note, id=note_id, user=request.user)
    tag_id = request.POST.get('tag_id')
    tag_name = request.POST.get('name', '').strip().replace('#', '').lower()

    tag = None
    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, user=request.user)
    elif tag_name:
        tag, _ = Tag.objects.get_or_create(
            user=request.user,
            name=tag_name,
            defaults={'color': request.POST.get('color', '#818cf8')}
        )

    if not tag:
        return HttpResponseBadRequest("Etiqueta inválida.")

    if tag in note.tags.all():
        note.tags.remove(tag)
        action = 'removed'
    else:
        note.tags.add(tag)
        action = 'added'

    return JsonResponse({
        'status': 'ok',
        'action': action,
        'tag': {'id': str(tag.id), 'name': tag.name, 'color': tag.color},
        'tags': [{'id': str(t.id), 'name': t.name, 'color': t.color} for t in note.tags.all()],
    })


@login_required
@require_POST
def tag_delete_view(request, tag_id):
    """Exclui uma etiqueta criada pelo usuário."""
    tag = get_object_or_404(Tag, id=tag_id, user=request.user)
    tag.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'deleted', 'tag_id': str(tag_id)})
    return redirect('notes:app')


@login_required
@require_POST
def toggle_note_share_view(request, note_id):
    """
    Ativa ou desativa o link público de compartilhamento de uma anotação.
    FBV: Function-Based View.
    """
    note = get_object_or_404(Note, id=note_id, user=request.user, is_deleted=False)

    action = request.POST.get('action')
    if action == 'disable' or (action is None and note.is_shared):
        note.disable_sharing()
        return JsonResponse({
            'status': 'ok',
            'is_shared': False,
            'share_url': '',
            'message': 'Compartilhamento por link desativado com sucesso.'
        })
    else:
        token = note.enable_sharing()
        share_url = request.build_absolute_uri(
            reverse('shared_note_root', kwargs={'share_token': token})
        )
        return JsonResponse({
            'status': 'ok',
            'is_shared': True,
            'share_url': share_url,
            'token': token,
            'message': 'Link público gerado com sucesso.'
        })


def shared_note_view(request, share_token):
    """
    Página pública para leitura de anotação compartilhada via link seguro.
    Não requer autenticação.
    FBV: Function-Based View.
    """
    note = get_object_or_404(
        Note.objects.select_related('notebook', 'user').prefetch_related('tags'),
        share_token=share_token,
        is_shared=True,
        is_deleted=False
    )

    context = {
        'note': note,
        'share_url': request.build_absolute_uri(),
    }
    return render(request, 'notes/shared_note.html', context)
