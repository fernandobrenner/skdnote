import io
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.text import slugify

from notes.models import Note
from .services import (
    build_note_markdown,
    generate_note_pdf,
    generate_note_docx,
    generate_user_backup_zip,
    sanitize_filename,
)


@login_required
def export_note_markdown_view(request, note_id):
    """
    Exporta uma única anotação ativa do usuário em formato Markdown (.md).
    FBV: Function-Based View.
    """
    note = get_object_or_404(
        Note.objects.select_related("notebook").prefetch_related("tags"),
        id=note_id,
        user=request.user,
        deleted_at__isnull=True
    )

    markdown_text = build_note_markdown(note)
    safe_title = slugify(note.title) or "nota"
    filename = f"{safe_title}.md"

    response = HttpResponse(markdown_text, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_note_html_view(request, note_id):
    """
    Exibe a anotação em um layout limpo para impressão/salvamento em PDF
    ou faz o download direto do arquivo .html caso ?download=1 seja passado.
    FBV: Function-Based View.
    """
    note = get_object_or_404(
        Note.objects.select_related("notebook").prefetch_related("tags"),
        id=note_id,
        user=request.user,
        deleted_at__isnull=True
    )

    is_download = request.GET.get("download") == "1"

    context = {
        "note": note,
    }

    if is_download:
        rendered_html = render(request, "exports/note_print.html", context).content
        safe_title = slugify(note.title) or "nota"
        filename = f"{safe_title}.html"

        response = HttpResponse(rendered_html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    return render(request, "exports/note_print.html", context)


@login_required
def export_backup_zip_view(request):
    """
    Gera e entrega o download de um arquivo .ZIP contendo todas as anotações
    do usuário organizadas em pastas de cadernos, arquivos Markdown e manifest.json.
    FBV: Function-Based View.
    """
    zip_bytes = generate_user_backup_zip(request.user)

    today_str = timezone.now().strftime("%Y-%m-%d")
    filename = f"skdnote-backup-{today_str}.zip"

    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(zip_bytes)
    return response


@login_required
def export_note_pdf_view(request, note_id):
    """
    Exporta uma única anotação do usuário em formato PDF profissional (.pdf).
    FBV: Function-Based View.
    """
    note = get_object_or_404(
        Note.objects.select_related("notebook").prefetch_related("tags"),
        id=note_id,
        user=request.user,
        deleted_at__isnull=True
    )

    pdf_bytes = generate_note_pdf(note)
    safe_title = slugify(note.title) or "nota"
    filename = f"{safe_title}.pdf"

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(pdf_bytes)
    return response


@login_required
def export_note_docx_view(request, note_id):
    """
    Exporta uma única anotação do usuário em formato Microsoft Word (.docx).
    FBV: Function-Based View.
    """
    note = get_object_or_404(
        Note.objects.select_related("notebook").prefetch_related("tags"),
        id=note_id,
        user=request.user,
        deleted_at__isnull=True
    )

    docx_bytes = generate_note_docx(note)
    safe_title = slugify(note.title) or "nota"
    filename = f"{safe_title}.docx"

    response = HttpResponse(
        docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(docx_bytes)
    return response
