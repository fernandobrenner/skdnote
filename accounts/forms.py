from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    PasswordChangeForm,
)
from django.core.exceptions import ValidationError
from .models import User, Currency


class CustomUserCreationForm(forms.ModelForm):
    """Formulário de cadastro de novo cliente com validação de senha e aceite LGPD."""
    full_name = forms.CharField(
        label="Nome Completo",
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Seu nome completo',
            'class': 'form-input',
            'autocomplete': 'name',
            'required': 'required',
        })
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'class': 'form-input',
            'autocomplete': 'email',
            'required': 'required',
        })
    )
    preferred_currency = forms.ChoiceField(
        label="Moeda de Cobrança Preferida",
        choices=Currency.choices,
        initial=Currency.BRL,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Mínimo de 8 caracteres',
            'class': 'form-input',
            'autocomplete': 'new-password',
            'required': 'required',
        }),
        min_length=8,
        help_text="Crie uma senha forte com no mínimo 8 caracteres."
    )
    password_confirm = forms.CharField(
        label="Confirmar Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repita sua senha',
            'class': 'form-input',
            'autocomplete': 'new-password',
            'required': 'required',
        })
    )
    accept_terms = forms.BooleanField(
        label="Concordo com os Termos de Uso e com a Política de Privacidade (LGPD)",
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
        })
    )

    class Meta:
        model = User
        fields = ('full_name', 'email', 'preferred_currency')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "As senhas informadas não coincidem.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Formulário de login utilizando e-mail como credencial principal."""
    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'class': 'form-input',
            'autocomplete': 'email',
            'autofocus': True,
            'required': 'required',
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Sua senha',
            'class': 'form-input',
            'autocomplete': 'current-password',
            'required': 'required',
        })
    )
    remember_me = forms.BooleanField(
        label="Lembrar deste dispositivo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
        })
    )

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            email = email.strip().lower()
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class CustomPasswordResetForm(PasswordResetForm):
    """Formulário customizado de solicitação de redefinição de senha."""
    email = forms.EmailField(
        label="Seu E-mail Cadastrado",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'class': 'form-input',
            'autocomplete': 'email',
            'required': 'required',
            'autofocus': True,
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    """Formulário para definição da nova senha após validação do token."""
    new_password1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Mínimo de 8 caracteres',
            'class': 'form-input',
            'autocomplete': 'new-password',
            'required': 'required',
        }),
        min_length=8,
    )
    new_password2 = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repita a nova senha',
            'class': 'form-input',
            'autocomplete': 'new-password',
            'required': 'required',
        })
    )


class CustomPasswordChangeForm(PasswordChangeForm):
    """Formulário para alteração de senha de usuário autenticado."""
    old_password = forms.CharField(
        label="Senha Atual",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Sua senha atual',
            'class': 'form-input',
            'autocomplete': 'current-password',
        })
    )
    new_password1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Mínimo de 8 caracteres',
            'class': 'form-input',
            'autocomplete': 'new-password',
        }),
        min_length=8,
    )
    new_password2 = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repita a nova senha',
            'class': 'form-input',
            'autocomplete': 'new-password',
        })
    )
