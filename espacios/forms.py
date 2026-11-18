"""Formularios de Publicar espacio: captura y validación en servidor.

- FormularioEspacio            -> FormularioEspacioIH (paso 1: información general)
- FormularioPrecioYHorarios    -> PantallaPrecioYHorarios (paso 2: precio y tarifa)
- FormularioHorario + conjunto -> filas de horarios de la PantallaPrecioYHorarios
Los mensajes son los de la especificación (PublicarEspacioService.MENSAJES).
"""
from django import forms
from django.forms import BaseFormSet, formset_factory
from PIL import Image, UnidentifiedImageError

from espacios.models import Fotografia, HorarioDisponible, Tarifa
from espacios.servicios.publicar_espacio import MENSAJES


class SelectorMultiple(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoFotografias(forms.FileField):
    """Acepta varios archivos y devuelve [(archivo, formato), ...] (A2)."""

    widget = SelectorMultiple(attrs={'accept': 'image/jpeg,image/png'})

    def clean(self, datos, inicial=None):
        archivos = datos if isinstance(datos, (list, tuple)) else ([datos] if datos else [])
        validas = []
        for archivo in archivos:
            formato = self._formato(archivo)
            if formato not in Fotografia.FORMATOS_PERMITIDOS:
                raise forms.ValidationError(MENSAJES['formato_fotografias'], code='formato')
            validas.append((archivo, formato))
        return validas

    @staticmethod
    def _formato(archivo):
        """Abre el archivo con Pillow para confirmar que de verdad es una imagen."""
        try:
            imagen = Image.open(archivo)
            imagen.verify()
            formato = imagen.format
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            formato = None
        archivo.seek(0)
        return formato


class FormularioEspacio(forms.Form):
    nombre = forms.CharField(
        label='Nombre del espacio', max_length=150,
        error_messages={'required': MENSAJES['nombre']},
        widget=forms.TextInput(attrs={'placeholder': 'Ej. Sala de juntas Central'}),
    )
    descripcion = forms.CharField(
        label='Descripción',
        error_messages={'required': MENSAJES['descripcion']},
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe el espacio'}),
    )
    capacidad = forms.IntegerField(
        label='Capacidad', min_value=1,
        error_messages={'required': MENSAJES['capacidad'], 'min_value': MENSAJES['capacidad']},
        widget=forms.NumberInput(attrs={'placeholder': 'Ej. 10'}),
    )
    direccion = forms.CharField(
        label='Dirección', max_length=255,
        error_messages={'required': MENSAJES['direccion']},
        widget=forms.TextInput(attrs={'placeholder': 'Calle, número, colonia'}),
    )
    fotografias = CampoFotografias(label='Fotografías', required=False)

    def __init__(self, *args, fotografias_previas=0, **kwargs):
        """`fotografias_previas`: cuántas imágenes ya se guardaron en un envío anterior."""
        super().__init__(*args, **kwargs)
        self.fotografias_previas = fotografias_previas

    def clean(self):
        datos = super().clean()
        if 'fotografias' in datos and not datos['fotografias'] and not self.fotografias_previas:
            self.add_error('fotografias', MENSAJES['fotografias'])
        return datos

    def datos_generales(self):
        d = self.cleaned_data
        return {campo: d[campo] for campo in ('nombre', 'descripcion', 'capacidad', 'direccion')}


class FormularioPrecioYHorarios(forms.Form):
    precio = forms.DecimalField(
        label='Precio (MXN)', max_digits=10, decimal_places=2,
        error_messages={'required': MENSAJES['precio']},
        widget=forms.NumberInput(attrs={'placeholder': 'Ej. 350.00', 'step': '0.01'}),
    )
    periodo = forms.ChoiceField(
        label='Modalidad de tarifa',
        choices=[('', 'Seleccione un periodo')] + Tarifa.PERIODOS,
        error_messages={'required': MENSAJES['periodo'], 'invalid_choice': MENSAJES['periodo']},
    )

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio <= 0:
            raise forms.ValidationError(MENSAJES['precio'])
        return precio

    def tarifa(self):
        return Tarifa(precio=self.cleaned_data['precio'], periodo=self.cleaned_data['periodo'])


class FormularioHorario(forms.Form):
    dia = forms.ChoiceField(label='Día', choices=HorarioDisponible.DIAS)
    hora_inicio = forms.TimeField(label='Hora inicial', widget=forms.TimeInput(attrs={'type': 'time'}))
    hora_fin = forms.TimeField(label='Hora final', widget=forms.TimeInput(attrs={'type': 'time'}))
    disponible = forms.BooleanField(label='Disponible', required=False, initial=True)

    # Lo marca el conjunto cuando la fila es inválida o se repite (para resaltarla).
    con_error = False


class ConjuntoBaseHorarios(BaseFormSet):
    """Revisa los horarios en conjunto (A4): al menos uno, fin > inicio y sin repetidos."""

    def _filas(self):
        """Formularios con datos que no se marcaron para eliminar."""
        return [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE')]

    @staticmethod
    def _horario(form):
        datos = {campo: valor for campo, valor in form.cleaned_data.items() if campo != 'DELETE'}
        return HorarioDisponible(**datos)

    def clean(self):
        if any(self.errors):
            raise forms.ValidationError(MENSAJES['horarios'])
        filas = [(form, self._horario(form)) for form in self._filas()]
        hay_error = not filas
        for form, horario in filas:
            if not horario.es_valido():
                form.con_error = hay_error = True
        for i, (form, horario) in enumerate(filas):
            for otro_form, otro in filas[i + 1:]:
                if horario.se_superpone_con(otro):
                    form.con_error = otro_form.con_error = hay_error = True
        if hay_error:
            raise forms.ValidationError(MENSAJES['horarios'])

    def horarios(self):
        """Horarios capturados como instancias de HorarioDisponible (sin guardar)."""
        return [self._horario(form) for form in self._filas()]


ConjuntoHorarios = formset_factory(
    FormularioHorario, formset=ConjuntoBaseHorarios, extra=0, can_delete=True,
)
