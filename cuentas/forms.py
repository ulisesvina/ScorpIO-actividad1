"""Formularios del registro: captura y validación en servidor."""
import re

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from cuentas.models import Usuario

# Estructura estándar del RFC mexicano: 3 letras (persona moral) o 4 (persona
# física), fecha AAMMDD y homoclave de 3 caracteres. No se valida la fecha ni el
# dígito verificador. Regla adicional a los documentos: ver ANOTACIONES_DOCUMENTACION.md
PATRON_RFC = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')

TIPO_CLIENTE = 'cliente'
TIPO_EMPRESA = 'empresa'


class FormularioRegistro(forms.Form):
    tipo_cuenta = forms.ChoiceField(
        label='Tipo de cuenta',
        choices=[(TIPO_CLIENTE, 'Cliente'), (TIPO_EMPRESA, 'Empresa')],
        initial=TIPO_CLIENTE,
        widget=forms.RadioSelect,
        error_messages={'invalid_choice': 'Selecciona Cliente o Empresa.'},
    )
    nombre = forms.CharField(label='Nombre', max_length=150)
    correo = forms.EmailField(
        label='Correo electrónico', max_length=254,
        error_messages={'invalid': 'Ingresa un correo electrónico válido.'},
    )
    password1 = forms.CharField(
        label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Confirmación de contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    rfc = forms.CharField(label='RFC o registro fiscal', max_length=20, required=False)

    # Se llena en clean_correo y lo usa la plantilla para ofrecer iniciar sesión.
    correo_ya_activo = False

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip().lower()
        if Usuario.objects.filter(correo=correo, is_active=True).exists():
            self.correo_ya_activo = True
            raise ValidationError('Ya existe una cuenta con ese correo electrónico.')
        return correo

    def clean_rfc(self):
        return re.sub(r'\s+', '', self.cleaned_data.get('rfc', '')).upper()

    def clean(self):
        datos = super().clean()
        es_empresa = datos.get('tipo_cuenta') == TIPO_EMPRESA

        if es_empresa:
            rfc = datos.get('rfc', '')
            if not rfc:
                self.add_error('rfc', 'Ingresa el RFC o registro fiscal de la empresa.')
            elif not PATRON_RFC.match(rfc):
                self.add_error('rfc', 'El RFC no tiene un formato válido (12 caracteres para persona moral, 13 para persona física).')
        else:
            datos['rfc'] = ''  # un Cliente nunca guarda datos de Empresa

        p1, p2 = datos.get('password1'), datos.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            else:
                usuario_temporal = Usuario(correo=datos.get('correo', ''), nombre=datos.get('nombre', ''))
                try:
                    password_validation.validate_password(p1, usuario_temporal)
                except ValidationError as error:
                    self.add_error('password1', error)
        return datos

    def datos_de_registro(self):
        """Datos ya validados, en el formato que espera el servicio."""
        d = self.cleaned_data
        return {
            'nombre': d['nombre'],
            'correo': d['correo'],
            'password': d['password1'],
            'es_empresa': d['tipo_cuenta'] == TIPO_EMPRESA,
            'rfc': d['rfc'],
        }


class FormularioReenvio(forms.Form):
    correo = forms.EmailField(
        label='Correo electrónico',
        error_messages={'invalid': 'Ingresa un correo electrónico válido.'},
    )

    def clean_correo(self):
        return self.cleaned_data['correo'].strip().lower()
