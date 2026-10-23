from django.urls import path
from .views import (
    app_view,
    note_create_view,
    note_autosave_view,
    note_toggle_pin_view,
    note_toggle_favorite_view,
    note_move_to_trash_view,
    note_restore_view,
    note_delete_permanent_view,
    notebook_create_view,
    notebook_delete_view,
    tag_create_view,
    tag_delete_view,
    note_tag_toggle_view,
    toggle_note_share_view,
    shared_note_view,
)

app_name = 'notes'

urlpatterns = [
    # Interface Principal UpNote (3 Colunas / Mobile)
    path('', app_view, name='app'),

    # Gestão de Notas
    path('create/', note_create_view, name='note_create'),
    path('<uuid:note_id>/autosave/', note_autosave_view, name='note_autosave'),
    path('<uuid:note_id>/pin/', note_toggle_pin_view, name='note_toggle_pin'),
    path('<uuid:note_id>/favorite/', note_toggle_favorite_view, name='note_toggle_favorite'),
    path('<uuid:note_id>/trash/', note_move_to_trash_view, name='note_move_to_trash'),
    path('<uuid:note_id>/restore/', note_restore_view, name='note_restore'),
    path('<uuid:note_id>/delete/', note_delete_permanent_view, name='note_delete_permanent'),
    path('<uuid:note_id>/share/', toggle_note_share_view, name='note_toggle_share'),
    path('<uuid:note_id>/tags/toggle/', note_tag_toggle_view, name='note_tag_toggle'),
    path('share/<str:share_token>/', shared_note_view, name='shared_note'),

    # Cadernos e Tags
    path('notebooks/create/', notebook_create_view, name='notebook_create'),
    path('notebooks/<uuid:notebook_id>/delete/', notebook_delete_view, name='notebook_delete'),
    path('tags/create/', tag_create_view, name='tag_create'),
    path('tags/<uuid:tag_id>/delete/', tag_delete_view, name='tag_delete'),
]
