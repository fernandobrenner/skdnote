import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import UUIDModel, TimeStampedModel


class Notebook(UUIDModel, TimeStampedModel):
    """Caderno para organização hierárquica de anotações (estilo UpNote)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notebooks',
        verbose_name="Usuário"
    )
    title = models.CharField(max_length=150, verbose_name="Título do Caderno")
    icon = models.CharField(max_length=50, default="📁", verbose_name="Ícone")
    color = models.CharField(max_length=20, default="#6366f1", verbose_name="Cor")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subnotebooks',
        verbose_name="Caderno Pai"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")

    class Meta:
        verbose_name = "Caderno"
        verbose_name_plural = "Cadernos"
        ordering = ['order', 'title']

    def __str__(self):
        if self.parent:
            return f"{self.parent.title} / {self.title}"
        return self.title

    @property
    def is_subnotebook(self):
        return self.parent is not None

    def active_notes_count(self):
        return self.notes.filter(is_deleted=False).count()


class Tag(UUIDModel, TimeStampedModel):
    """Etiqueta para classificação transversal de notas."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tags',
        verbose_name="Usuário"
    )
    name = models.CharField(max_length=50, verbose_name="Nome da Tag")
    color = models.CharField(max_length=20, default="#818cf8", verbose_name="Cor da Tag")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return f"#{self.name}"

    def active_notes_count(self):
        return self.notes.filter(is_deleted=False).count()


class Note(UUIDModel, TimeStampedModel):
    """Modelo central de anotação com suporte a rich text, markdown e autosave."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name="Usuário"
    )
    notebook = models.ForeignKey(
        Notebook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
        verbose_name="Caderno"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='notes',
        verbose_name="Tags"
    )

    title = models.CharField(max_length=255, default="Sem título", verbose_name="Título")
    content_json = models.JSONField(default=dict, blank=True, verbose_name="Conteúdo Estruturado (JSON)")
    content_html = models.TextField(blank=True, verbose_name="Conteúdo HTML")
    content_plain = models.TextField(blank=True, verbose_name="Texto Puro (para busca e prévias)")

    # Flags de organização e estados UpNote
    is_pinned = models.BooleanField(default=False, verbose_name="Fixada no Topo")
    is_favorite = models.BooleanField(default=False, verbose_name="Favorita")
    is_archived = models.BooleanField(default=False, verbose_name="Arquivada")

    # Compartilhamento público por link seguro
    is_shared = models.BooleanField(default=False, verbose_name="Compartilhada via Link")
    share_token = models.CharField(max_length=64, blank=True, null=True, unique=True, verbose_name="Token de Compartilhamento")
    share_created_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Compartilhamento")
    
    # Soft delete (Lixeira)
    is_deleted = models.BooleanField(default=False, verbose_name="Na Lixeira")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Exclusão")

    class Meta:
        verbose_name = "Anotação"
        verbose_name_plural = "Anotações"
        ordering = ['-is_pinned', '-updated_at']

    def __str__(self):
        return self.title or "Sem título"

    def generate_share_token(self):
        """Gera um token único e seguro para compartilhamento da nota."""
        import secrets
        while True:
            token = secrets.token_urlsafe(16)
            if not Note.objects.filter(share_token=token).exists():
                return token

    def enable_sharing(self):
        """Habilita o compartilhamento público via link."""
        if not self.share_token:
            self.share_token = self.generate_share_token()
        self.is_shared = True
        self.share_created_at = timezone.now()
        self.save(update_fields=['is_shared', 'share_token', 'share_created_at', 'updated_at'])
        return self.share_token

    def disable_sharing(self):
        """Desativa o compartilhamento público."""
        self.is_shared = False
        self.save(update_fields=['is_shared', 'updated_at'])

    def move_to_trash(self):
        """Move a anotação para a lixeira (soft delete)."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def restore_from_trash(self):
        """Restaura a anotação da lixeira."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def preview_text(self, length=90):
        """Retorna uma prévia curta do texto para a listagem lateral."""
        if not self.content_plain:
            return "Nota vazia"
        lines = [line.strip() for line in self.content_plain.split('\n') if line.strip()]
        text = " ".join(lines)
        if len(text) > length:
            return text[:length] + "..."
        return text or "Nota vazia"


class NoteAttachment(UUIDModel, TimeStampedModel):
    """Anexo de mídia ou documento inserido em uma anotação."""
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="Anotação"
    )
    file = models.FileField(upload_to='attachments/%Y/%m/', verbose_name="Arquivo")
    file_name = models.CharField(max_length=255, verbose_name="Nome do Arquivo")
    file_type = models.CharField(max_length=100, blank=True, verbose_name="Tipo MIME")
    file_size = models.PositiveIntegerField(default=0, verbose_name="Tamanho em Bytes")

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"

    def __str__(self):
        return self.file_name


class NoteVersion(UUIDModel):
    """Snapshot histórico da anotação para restauração de versões."""
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Anotação"
    )
    title = models.CharField(max_length=255, verbose_name="Título no Snapshot")
    content_html = models.TextField(blank=True, verbose_name="Conteúdo HTML no Snapshot")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Versão da Nota"
        verbose_name_plural = "Versões da Nota"
        ordering = ['-created_at']
