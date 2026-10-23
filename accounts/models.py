from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from core.models import UUIDModel, TimeStampedModel


class UserType(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrador'
    CUSTOMER = 'CUSTOMER', 'Cliente'


class Currency(models.TextChoices):
    BRL = 'BRL', 'R$ (Real Brasileiro)'
    USD = 'USD', '$ (Dólar Americano)'
    EUR = 'EUR', '€ (Euro)'


class CustomUserManager(BaseUserManager):
    """Gerenciador de usuário personalizado que utiliza o e-mail como identificador único."""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O endereço de e-mail é obrigatório.')
        email = self.normalize_email(email)
        extra_fields.setdefault('role', UserType.CUSTOMER)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', UserType.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuário deve ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuário deve ter is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    """Modelo de usuário customizado usando e-mail para autenticação."""
    email = models.EmailField(unique=True, db_index=True, verbose_name="E-mail")
    full_name = models.CharField(max_length=255, blank=True, verbose_name="Nome Completo")
    role = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.CUSTOMER,
        verbose_name="Tipo de Usuário"
    )
    preferred_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.BRL,
        verbose_name="Moeda Preferida"
    )

    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    is_staff = models.BooleanField(default=False, verbose_name="Acesso à Administração")

    # Preferências visuais da interface
    theme = models.CharField(
        max_length=10,
        choices=[('light', 'Claro'), ('dark', 'Escuro'), ('system', 'Sistema')],
        default='system',
        verbose_name="Tema Visual"
    )
    editor_font = models.CharField(
        max_length=10,
        choices=[('sans', 'Sem serifa'), ('serif', 'Com serifa'), ('mono', 'Monoespaçada')],
        default='sans',
        verbose_name="Fonte do Editor"
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        return self.role == UserType.ADMIN or self.is_superuser

    @property
    def is_customer(self):
        return self.role == UserType.CUSTOMER

    def get_short_name(self):
        if self.full_name:
            return self.full_name.split()[0]
        return self.email.split('@')[0]


class ConsentLog(UUIDModel, TimeStampedModel):
    """Registro de consentimento LGPD para auditoria jurídica e compliance."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='consent_logs',
        null=True,
        blank=True,
        verbose_name="Usuário"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Endereço IP")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="Navegador/User Agent")
    terms_version = models.CharField(max_length=20, default="1.0", verbose_name="Versão dos Termos")
    privacy_policy_version = models.CharField(max_length=20, default="1.0", verbose_name="Versão da Política")
    accepted_cookies_essential = models.BooleanField(default=True)
    accepted_cookies_analytics = models.BooleanField(default=False)
    accepted_cookies_marketing = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Registro de Consentimento LGPD"
        verbose_name_plural = "Registros de Consentimento LGPD"
        ordering = ['-created_at']

    def __str__(self):
        user_str = self.user.email if self.user else "Anônimo"
        return f"Consentimento de {user_str} em {self.created_at:%d/%m/%Y %H:%M}"
