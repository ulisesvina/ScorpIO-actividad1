"""Formulario de inicio de sesión (DatosInicioSesion)."""
from django import forms


class FormularioInicioSesion(forms.Form):
    correo = forms.EmailField(
        label='Correo electrónico', max_length=254,
        error_messages={
            'required': 'Ingresa tu correo electrónico.',
            'invalid': 'Ingresa un correo electrónico válido.',
        },
    )
    password = forms.CharField(
        label='Contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),  # no se vuelve a mostrar
        error_messages={'required': 'Ingresa tu contraseña.'},
    )

    def clean_correo(self):
        return self.cleaned_data['correo'].strip().lower()

    def clean(self):
        datos = super().clean()
        if self.has_error('correo', 'required') or self.has_error('password', 'required'):
            self.add_error(None, 'Ambos campos son obligatorios.')
        return datos
