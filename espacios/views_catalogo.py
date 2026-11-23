"""Vistas de Ver espacio (EspacioController).

- buscar_espacios -> BuscarEspaciosIH (lista de tarjetas, filtros, A2 y avisos)
- detalle_espacio -> pantalla detallada del espacio (A3)
"""
import logging

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from espacios.forms_busqueda import FormularioBusqueda
from espacios.servicios import consulta_espacios as consulta

logger = logging.getLogger(__name__)

MENSAJE_NO_DISPONIBLE = 'El espacio consultado ya no se encuentra disponible'
MENSAJE_SIN_RESULTADOS = 'No se encontraron espacios disponibles con los criterios ingresados'
MENSAJE_ERROR_CARGA = 'No fue posible cargar la información del espacio. Por favor, reintenta más tarde'
POLITICAS = (
    'Las reservas no se pueden modificar ni reagendar: para hacer un cambio, cancela la '
    'reserva y genera una nueva. La cancelación se rige por las políticas de la plataforma.'
)

# Avisos que el catálogo acepta por ?aviso=... (solo estos valores, nunca texto libre).
AVISOS = {'no_disponible': MENSAJE_NO_DISPONIBLE}


def _pantalla_error(request):
    """E1: falla de base de datos. Se muestra el catálogo vacío con el aviso."""
    return render(request, 'espacios/buscar_espacios.html', {
        'form': FormularioBusqueda(), 'espacios': [], 'sin_resultados': False,
        'aviso': MENSAJE_ERROR_CARGA, 'mensaje_sin_resultados': MENSAJE_SIN_RESULTADOS,
    })


@login_required
@require_GET
def buscar_espacios(request):
    form = FormularioBusqueda(request.GET or None)
    criterios = {}
    if form.is_bound and form.is_valid():
        criterios = {campo: valor for campo, valor in form.cleaned_data.items() if valor}
    try:
        espacios = consulta.buscar(**criterios)
    except DatabaseError:
        logger.exception('Error de base de datos al buscar espacios')
        return _pantalla_error(request)
    return render(request, 'espacios/buscar_espacios.html', {
        'form': form,
        'espacios': espacios,
        'sin_resultados': bool(criterios) and not espacios,  # A2
        'aviso': AVISOS.get(request.GET.get('aviso')),       # A3
        'mensaje_sin_resultados': MENSAJE_SIN_RESULTADOS,
    })


@login_required
@require_GET
def detalle_espacio(request, id_espacio):
    try:
        espacio = consulta.obtener_publicado(id_espacio)
        horarios = consulta.horarios_disponibles(espacio)
        fotografias = list(espacio.fotografias.all())
    except consulta.EspacioNoDisponible:  # A3
        return redirect(reverse('espacios:buscar_espacios') + '?aviso=no_disponible')
    except DatabaseError:  # E1
        logger.exception('Error de base de datos al consultar el espacio %s', id_espacio)
        return _pantalla_error(request)
    return render(request, 'espacios/detalle_espacio.html', {
        'espacio': espacio,
        'horarios': horarios,
        'fotografias': fotografias,
        'politicas': POLITICAS,
    })