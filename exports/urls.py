from django.urls import path
from .views import (
    export_note_markdown_view,
    export_note_html_view,
    export_note_pdf_view,
    export_note_docx_view,
    export_backup_zip_view,
)

app_name = "exports"

urlpatterns = [
    # Exportação individual de nota
    path("note/<uuid:note_id>/markdown/", export_note_markdown_view, name="note_markdown"),
    path("note/<uuid:note_id>/html/", export_note_html_view, name="note_html"),
    path("note/<uuid:note_id>/pdf/", export_note_pdf_view, name="note_pdf"),
    path("note/<uuid:note_id>/docx/", export_note_docx_view, name="note_docx"),

    # Backup completo da conta (ZIP com todas as notas e cadernos)
    path("backup/zip/", export_backup_zip_view, name="backup_zip"),
]
