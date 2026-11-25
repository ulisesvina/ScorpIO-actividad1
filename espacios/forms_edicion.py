"""Formularios de Editar espacio.

- FormularioEdicionEspacio -> FormularioEspacioIH en modo edición (DatosEdicionEspacio):
  los mismos campos que al publicar más dimensionesM2 (opcional)
Precio, modalidad y horarios usan los mismos formularios de Publicar espacio.
"""
from decimal import Decimal

from django import forms

from espacios.forms import FormularioEspacio

MENSAJE_DIMENSIONES = 'Las dimensiones deben ser mayores que cero'


class FormularioEdicionEspacio(FormularioEspacio):
    dimensiones_m2 = forms.DecimalField(
        label='Dimensiones (m²)', required=False, max_digits=8, decimal_places=2,
        min_value=Decimal('0.01'),
        error_messages={'min_value': MENSAJE_DIMENSIONES, 'invalid': MENSAJE_DIMENSIONES},
        widget=forms.NumberInput(attrs={'placeholder': 'Ej. 45.5', 'step': '0.01'}),
    )

    field_order = ['nombre', 'descripcion', 'capacidad', 'direccion', 'dimensiones_m2', 'fotografias']

    def datos_generales(self):
        """Como texto para poder guardarse en la sesión (JSON)."""
        datos = super().datos_generales()
        dimensiones = self.cleaned_data.get('dimensiones_m2')
        datos['dimensiones_m2'] = str(dimensiones) if dimensiones is not None else None
        return datos
