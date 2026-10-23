import uuid
from django.db import models


class UUIDModel(models.Model):
    """Modelo base abstrato que utiliza UUID como chave primária."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Modelo base abstrato que adiciona timestamps automáticos."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        abstract = True


class SystemAnnouncement(UUIDModel, TimeStampedModel):
    """Avisos globais emitidos por administradores para todos os usuários."""
    class Level(models.TextChoices):
        INFO = 'INFO', 'Informativo'
        WARNING = 'WARNING', 'Aviso'
        CRITICAL = 'CRITICAL', 'Crítico'

    title = models.CharField(max_length=200, verbose_name="Título")
    message = models.TextField(verbose_name="Mensagem")
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO, verbose_name="Nível")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expira em")

    class Meta:
        verbose_name = "Aviso do Sistema"
        verbose_name_plural = "Avisos do Sistema"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.level}] {self.title}"
