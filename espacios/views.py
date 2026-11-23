"""Vistas de Publicar espacio (EspacioController).

Pantallas (diagrama de clases / navegación):
- mis_espacios        -> MisEspaciosIH
- formulario_espacio  -> FormularioEspacioIH        (paso 1 de 3)
- precio_y_horarios   -> PantallaPrecioYHorarios    (paso 2 de 3)
- revisar_y_publicar  -> PantallaRevisarYPublicar   (paso 3 de 3)
- espacio_publicado   -> EspacioPublicadoIH
- vincular_calendario -> precondición: Google Calendar vinculado

Hasta que se publica, lo capturado vive en la sesión (no en la base de datos), igual
que en el diagrama de secuencia, donde nada se guarda antes de crearEspacio().
"""
import logging
from datetime import time
from decimal import Decimal
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from espacios.forms import (
    ConjuntoHorarios, FormularioEspacio, FormularioPrecioYHorarios, FormularioVincularCalendario,
)
from espacios.models import Espacio, HorarioDisponible, Tarifa
from espacios.servicios import almacen_imagenes, google_calendar
from espacios.servicios import publicar_espacio as servicio

logger = logging.getLogger(__name__)

SESION_BORRADOR = 'publicar_espacio'

# Mensajes de la especificación (flujo normal y flujos excepcionales).
MENSAJE_SINCRONIZADO = 'Datos guardados y calendario sincronizado'
MENSAJE_CONFLICTO_PARCIAL = (
    'Algunos horarios ya están ocupados en Google Calendar. Solo se publicarán los horarios disponibles.'
)
MENSAJE_SINCRONIZACION_PENDIENTE = 'Google Calendar conectado. Sincronización pendiente.'
MENSAJE_FALLA_CALENDARIO = 'No fue posible sincronizar el calendario. Intente nuevamente más tarde'
MENSAJE_FALLA_PUBLICAR = 'No fue posible publicar el espacio. Intente nuevamente más tarde'
MENSAJE_FALLA_IMAGENES = 'Ocurrió un problema al guardar las imágenes. Intente nuevamente'
MENSAJE_CALENDARIO_SIN_ACCESO = (
    'No fue posible acceder a su Google Calendar. Verifique que lo compartió con %s'
)
MENSAJE_PUBLICADO = 'El espacio se publicó correctamente'


# --- Acceso -----------------------------------------------------------------

def empresa_requerida(vista):
    """Solo una cuenta de Empresa con sesión iniciada puede publicar espacios."""

    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        empresa = getattr(request.user, 'empresa', None) if request.user.es_empresa else None
        if empresa is None:
            raise PermissionDenied('Solo las cuentas de Empresa pueden publicar espacios.')
        request.empresa = empresa
        return vista(request, *args, **kwargs)

    return envoltura


# --- Borrador en sesión -----------------------------------------------------

def _borrador(request):
    return request.session.get(SESION_BORRADOR, {})


def _guardar_borrador(request, borrador):
    request.session[SESION_BORRADOR] = borrador


def _horario_a_sesion(horario, activo, ocupado=False):
    return {
        'dia': horario.dia,
        'hora_inicio': horario.hora_inicio.strftime('%H:%M'),
        'hora_fin': horario.hora_fin.strftime('%H:%M'),
        'activo': activo,      # la Empresa lo dejó marcado como disponible
        'ocupado': ocupado,    # Google Calendar lo reporta ocupado (A5)
    }


def _horario_de_sesion(datos):
    return HorarioDisponible(
        dia=datos['dia'],
        hora_inicio=time.fromisoformat(datos['hora_inicio']),
        hora_fin=time.fromisoformat(datos['hora_fin']),
        disponible=datos['activo'] and not datos['ocupado'],
    )


def _espacio_de_sesion(borrador, empresa):
    """Arma los objetos (sin guardar) a partir de lo capturado."""
    espacio = Espacio().capturar_datos(borrador['datos_generales'], empresa)
    tarifa = Tarifa(precio=Decimal(borrador['tarifa']['precio']), periodo=borrador['tarifa']['periodo'])
    horarios = [_horario_de_sesion(h) for h in borrador['horarios']]
    return espacio, tarifa, horarios


def _foto_para_mostrar(foto):
    return {**foto, 'url': almacen_imagenes.default_storage.url(foto['ruta'])}


# --- Pantallas --------------------------------------------------------------

@require_GET
@empresa_requerida
def mis_espacios(request):
    """MisEspaciosIH: espacios de la Empresa y opción «Publicar espacio»."""
    espacios = (
        request.empresa.espacios.select_related('tarifa').prefetch_related('fotografias').order_by('-id')
    )
    return render(request, 'espacios/mis_espacios.html', {'espacios': espacios})


@require_http_methods(['GET', 'POST'])
@empresa_requerida
def formulario_espacio(request):
    """FormularioEspacioIH (paso 1): nombre, descripción, capacidad, dirección y fotografías."""
    borrador = _borrador(request)
    fotos = borrador.get('fotografias', [])
    error_general = None

    if request.method == 'POST' and 'quitar_fotografia' in request.POST:
        indice = int(request.POST['quitar_fotografia'])
        if 0 <= indice < len(fotos):
            almacen_imagenes.descartar_temporales([fotos.pop(indice)])
            borrador['fotografias'] = fotos
            _guardar_borrador(request, borrador)
        form = FormularioEspacio(initial=request.POST.dict(), fotografias_previas=len(fotos))
    elif request.method == 'POST':
        form = FormularioEspacio(request.POST, request.FILES, fotografias_previas=len(fotos))
        valido = form.is_valid()
        nuevas = form.cleaned_data.get('fotografias', []) if 'fotografias' not in form.errors else []
        try:
            # Las imágenes válidas se conservan aunque otro campo tenga error (A1).
            for archivo, formato in nuevas:
                fotos.append(almacen_imagenes.guardar_temporal(archivo, formato))
        except almacen_imagenes.ErrorAlmacenamiento:
            error_general = MENSAJE_FALLA_IMAGENES  # E3
            valido = False
        borrador['fotografias'] = fotos
        if valido:
            borrador['datos_generales'] = form.datos_generales()
            borrador['calendario_sincronizado'] = False
            _guardar_borrador(request, borrador)
            return redirect('espacios:precio_y_horarios')  # continuarPublicar()
        _guardar_borrador(request, borrador)
    else:
        form = FormularioEspacio(initial=borrador.get('datos_generales'), fotografias_previas=len(fotos))

    return render(request, 'espacios/formulario_espacio.html', {
        'form': form,
        'fotografias': [_foto_para_mostrar(f) for f in fotos],
        'error_general': error_general,
    })


def _formularios_paso_2(borrador, datos=None):
    """FormularioPrecioYHorarios y ConjuntoHorarios, con lo guardado en el borrador."""
    if datos is not None:
        return FormularioPrecioYHorarios(datos), ConjuntoHorarios(datos)
    horarios = borrador.get('horarios') or [
        {'dia': 'lunes', 'hora_inicio': '09:00', 'hora_fin': '18:00', 'activo': True, 'ocupado': False},
    ]
    iniciales = [
        {'dia': h['dia'], 'hora_inicio': h['hora_inicio'], 'hora_fin': h['hora_fin'], 'disponible': h['activo']}
        for h in horarios
    ]
    return FormularioPrecioYHorarios(initial=borrador.get('tarifa')), ConjuntoHorarios(initial=iniciales)


def _agregar_fila(datos):
    """agregarHorario(): añade una fila nueva conservando lo ya escrito."""
    datos = datos.copy()
    total = int(datos.get('form-TOTAL_FORMS', 0))
    datos['form-TOTAL_FORMS'] = str(total + 1)
    datos['form-INITIAL_FORMS'] = str(total + 1)
    datos.update({
        'form-%d-dia' % total: 'lunes',
        'form-%d-hora_inicio' % total: '09:00',
        'form-%d-hora_fin' % total: '18:00',
        'form-%d-disponible' % total: 'on',
    })
    return datos


def _hay_horarios_libres(borrador):
    return any(h['activo'] and not h['ocupado'] for h in borrador.get('horarios', []))


@require_http_methods(['GET', 'POST'])
@empresa_requerida
def precio_y_horarios(request):
    """PantallaPrecioYHorarios (paso 2): precio, modalidad, horarios y sincronización."""
    borrador = _borrador(request)
    if 'datos_generales' not in borrador:
        return redirect('espacios:formulario_espacio')
    empresa = request.empresa
    accion = request.POST.get('accion')
    contexto = {'mostrar_errores': False, 'aviso': None, 'aviso_tipo': None, 'error_modal': None}

    if accion == 'atras':
        return redirect('espacios:formulario_espacio')

    if request.method == 'GET':
        form, horarios_form = _formularios_paso_2(borrador)
    elif accion == 'agregar_horario':
        form, horarios_form = _formularios_paso_2(borrador, _agregar_fila(request.POST))
        borrador['calendario_sincronizado'] = False
        _guardar_borrador(request, borrador)
    else:
        form, horarios_form = _formularios_paso_2(borrador, request.POST)
        if not (form.is_valid() and horarios_form.is_valid()):
            contexto['mostrar_errores'] = True  # A3 / A4
        else:
            tarifa = form.tarifa()
            horarios = horarios_form.horarios()
            capturado = {
                'tarifa': {'precio': str(tarifa.precio), 'periodo': tarifa.periodo},
                'horarios': [_horario_a_sesion(h, h.disponible) for h in horarios],
            }
            sin_cambios = (
                borrador.get('calendario_sincronizado')
                and borrador.get('tarifa') == capturado['tarifa']
                and [{**h, 'ocupado': False} for h in borrador.get('horarios', [])] == capturado['horarios']
            )
            if accion == 'siguiente' and sin_cambios:
                if _hay_horarios_libres(borrador):
                    return redirect('espacios:revisar_y_publicar')  # continuar()
                contexto.update(aviso=servicio.MENSAJES['sin_horarios_libres'], aviso_tipo='error')
            elif accion == 'siguiente':
                borrador.update(capturado, calendario_sincronizado=False)
                _guardar_borrador(request, borrador)
                contexto.update(aviso=MENSAJE_SINCRONIZACION_PENDIENTE, aviso_tipo='pendiente')
            else:
                # guardarDatosYSincronizar(datos, empresa): pasos 8 a 14 de la secuencia.
                borrador.update(capturado, calendario_sincronizado=False)
                _guardar_borrador(request, borrador)
                contexto.update(_sincronizar(request, borrador, empresa, tarifa, horarios))
            form, horarios_form = _formularios_paso_2(borrador)

    sincronizado = borrador.get('calendario_sincronizado', False)
    estados = borrador['horarios'] if sincronizado else [None] * len(horarios_form.forms)
    contexto.update({
        'form': form,
        'horarios_form': horarios_form,
        'filas': list(zip(horarios_form.forms, estados)),
        'calendario_vinculado': bool(empresa.id_calendario),
        'sincronizado': sincronizado,
        'puede_continuar': sincronizado and _hay_horarios_libres(borrador),
    })
    return render(request, 'espacios/precio_y_horarios.html', contexto)


def _sincronizar(request, borrador, empresa, tarifa, horarios):
    """Revisa la información y sincroniza con Google Calendar. Devuelve datos para la pantalla."""
    espacio = Espacio().capturar_datos(borrador['datos_generales'], empresa)  # paso 9
    errores = servicio.revisar_informacion(espacio, tarifa, horarios, borrador.get('fotografias', []))
    errores.pop('horarios', None)  # los horarios libres se revisan después de sincronizar
    if errores:
        return {'aviso': next(iter(errores.values())), 'aviso_tipo': 'error'}
    if not empresa.id_calendario:
        return {}  # la pantalla ofrece «Vincular Google Calendar»
    try:
        en_conflicto = servicio.revisar_horarios(empresa, horarios)  # paso 12
    except google_calendar.CalendarioNoDisponible:
        return {'error_modal': MENSAJE_FALLA_CALENDARIO}  # E1
    except google_calendar.CalendarioSinAcceso:
        correo = google_calendar.correo_cuenta_de_servicio() or 'la cuenta de servicio de Reserva-Hub'
        return {'aviso': MENSAJE_CALENDARIO_SIN_ACCESO % correo, 'aviso_tipo': 'error'}

    for datos, horario in zip(borrador['horarios'], horarios):
        datos['ocupado'] = horario in en_conflicto
    borrador['calendario_sincronizado'] = True
    _guardar_borrador(request, borrador)

    if not _hay_horarios_libres(borrador):
        return {'aviso': servicio.MENSAJES['sin_horarios_libres'], 'aviso_tipo': 'error'}  # A5
    if en_conflicto:
        return {'aviso': MENSAJE_CONFLICTO_PARCIAL, 'aviso_tipo': 'pendiente'}  # A5 parcial
    return {'aviso': MENSAJE_SINCRONIZADO, 'aviso_tipo': 'exito'}  # paso 14


@require_http_methods(['GET', 'POST'])
@empresa_requerida
def revisar_y_publicar(request):
    """PantallaRevisarYPublicar (paso 3): resumen y «Publicar espacio» (pasos 16 a 37)."""
    borrador = _borrador(request)
    if 'datos_generales' not in borrador:
        return redirect('espacios:formulario_espacio')
    if not borrador.get('calendario_sincronizado'):
        return redirect('espacios:precio_y_horarios')

    empresa = request.empresa
    espacio, tarifa, horarios = _espacio_de_sesion(borrador, empresa)
    fotos = borrador.get('fotografias', [])
    error_modal = None
    errores = {}

    if request.method == 'POST':
        errores = servicio.revisar_informacion(espacio, tarifa, horarios, fotos)  # paso 19
        if not errores:
            espacio.publicar()  # paso 21
            try:
                servicio.crear_espacio(espacio, tarifa, horarios, fotos)  # paso 22
            except almacen_imagenes.ErrorAlmacenamiento:
                error_modal = MENSAJE_FALLA_IMAGENES  # E3
            except DatabaseError:
                error_modal = MENSAJE_FALLA_PUBLICAR  # E2
            else:
                del request.session[SESION_BORRADOR]
                return redirect('espacios:espacio_publicado', id_espacio=espacio.pk)

    return render(request, 'espacios/revisar_y_publicar.html', {
        'espacio': espacio,
        'tarifa': tarifa,
        'horarios': horarios,
        'fotografias': [_foto_para_mostrar(f) for f in fotos],
        'empresa': empresa,
        'errores': errores,
        'error_modal': error_modal,
    })


@require_GET
@empresa_requerida
def espacio_publicado(request, id_espacio):
    """EspacioPublicadoIH: confirmación con los datos del espacio publicado."""
    espacio = get_object_or_404(
        Espacio.objects.select_related('tarifa'), pk=id_espacio, empresa=request.empresa,
    )
    return render(request, 'espacios/espacio_publicado.html', {
        'espacio': espacio,
        'mensaje': MENSAJE_PUBLICADO,
    })


@require_POST
@empresa_requerida
def cancelar(request):
    """cancelar(): descarta lo capturado y regresa a Mis espacios."""
    borrador = request.session.pop(SESION_BORRADOR, {})
    almacen_imagenes.descartar_temporales(borrador.get('fotografias', []))
    return redirect('espacios:mis_espacios')


@require_http_methods(['GET', 'POST'])
@empresa_requerida
def vincular_calendario(request):
    """Vincula el Google Calendar de la Empresa (precondición del caso de uso)."""
    empresa = request.empresa
    correo = google_calendar.correo_cuenta_de_servicio()
    error = None
    if request.method == 'POST':
        form = FormularioVincularCalendario(request.POST)
        if form.is_valid():
            id_calendario = form.cleaned_data['id_calendario']
            try:
                google_calendar.consultar_eventos(id_calendario, *google_calendar.rango_de_consulta())
            except google_calendar.CalendarioSinAcceso:
                error = MENSAJE_CALENDARIO_SIN_ACCESO % (correo or 'la cuenta de servicio de Reserva-Hub')
            except google_calendar.CalendarioNoDisponible:
                error = MENSAJE_FALLA_CALENDARIO
            else:
                empresa.id_calendario = id_calendario
                empresa.save(update_fields=['id_calendario'])
                if 'datos_generales' in _borrador(request):
                    return redirect('espacios:precio_y_horarios')
                return redirect('espacios:mis_espacios')
    else:
        form = FormularioVincularCalendario(initial={'id_calendario': empresa.id_calendario})
    return render(request, 'espacios/vincular_calendario.html', {
        'form': form,
        'correo_servicio': correo,
        'error': error,
        'vinculado': bool(empresa.id_calendario),
    })
