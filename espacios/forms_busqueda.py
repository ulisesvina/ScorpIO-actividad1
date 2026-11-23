"""Filtros de la búsqueda de espacios (A1)."""
from django import forms


class FormularioBusqueda(forms.Form):
    q = forms.CharField(
        label='Buscar', required=False, max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Nombre o descripción'}),
    )
    ubicacion = forms.CharField(
        label='Ubicación', required=False, max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Calle, colonia...'}),
    )
    fecha = forms.DateField(
        label='Fecha', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        error_messages={'invalid': 'Ingrese una fecha válida'},
    )