"""Vistas de Editar espacio (EspacioControllerEditarEspacio).

Pantallas (diagrama de clases de Editar espacio):
- mis_espacios (views.py)  -> PantallaMisEspaciosIH, con el botón «Editar» (editarEspacios())
- abrir_edicion            -> abrirEdicion(idEmpresa, idEspacio) + FormularioEspacioIH.cargarDatos(espacio)
- editar_informacion       -> FormularioEspacioIH en modo edición       (paso 1 de 3)
- editar_precio_y_horarios -> PantallaPrecioYHorariosIH en modo edición (paso 2 de 3)
- revisar_y_guardar        -> PantallaRevisarYGuardar                   (paso 3 de 3)
- espacio_actualizado      -> PantallaRevisarYGuardar.mostrarMensaje() / volverAMisEspacios()
- cancelar_edicion         -> FormularioEspacioIH.cancelar() / DatosEdicionEspacio.descartar()

Igual que en Publicar espacio, lo capturado vive en la sesión (DatosEdicionEspacio) y la base
de datos no cambia hasta presionar «Guardar cambios». Se reutilizan las pantallas y las
utilidades de Publicar espacio (views.py) sin modificarlas.
"""
import logging
from decimal import Decimal
from functools import wraps

from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from espacios.forms_edicion import FormularioEdicionEspacio
from espacios.models import Tarifa
from espacios.servicios import almacen_imagenes, google_calendar
from espacios.servicios import editar_espacio as servicio
from espacios.views import (
    MENSAJE_CALENDARIO_SIN_ACCESO, MENSAJE_CONFLICTO_PARCIAL, MENSAJE_FALLA_CALENDARIO,
    MENSAJE_FALLA_IMAGENES, MENSAJE_SINCRONIZACION_PENDIENTE, MENSAJE_SINCRONIZADO,
    _agregar_fila, _foto_para_mostrar, _formularios_paso_2, _hay_horarios_libres,
    _horario_a_sesion, _horario_de_sesion, empresa_requerida,
)

logger = logging.getLogger(__name__)

SESION_EDICION = 'editar_espacio'
TITULO_CASO = 'Editar espacio'

MENSAJE_ACTUALIZADO = 'Los cambios del espacio se guardaron correctamente'
MENSAJE_FALLA_GUARDAR = 'No fue posible guardar los cambios. Intente nuevamente más tarde'


# --- Acceso -----------------------------------------------------------------

def espacio_editable(vista):
    """Solo la Empresa dueña puede editar el espacio (perteneceA) y solo si sigue publicado
    (estaDisponible). Deja el espacio en `request.espacio`."""

    @empresa_requerida
    @wraps(vista)
    def envoltura(request, id_espacio, *args, **kwargs):
        try:
            request.espacio = servicio.buscar_espacio(request.empresa, id_espacio)
        except servicio.EspacioNoEncontrado:
            raise Http404('El espacio no existe.')
        except servicio.EspacioNoEditable:
            return redirect('espacios:mis_espacios')
        return vista(request, id_espacio, *args, **kwargs)

    return envoltura


# --- DatosEdicionEspacio (borrador en sesión) --------------------------------

def _borrador(request, id_espacio):
    """El borrador del espacio indicado, o None si no se abrió su edición."""
    borrador = request.session.get(SESION_EDICION)
    if borrador and borrador.get('id_espacio') == id_espacio:
        return borrador
    return None


def _guardar_borrador(request, borrador):
    request.session[SESION_EDICION] = borrador


def _descartar(request):
    """descartar(): olvida lo capturado y borra solo las fotografías temporales."""
    borrador = request.session.pop(SESION_EDICION, None) or {}
    servicio.descartar_temporales(borrador.get('fotografias', []))


def _invalidar_sincronizacion(request, borrador):
    """invalidarSincronizacion(): el precio o los horarios cambiaron."""
    borrador['calendario_sincronizado'] = False
    _guardar_borrador(request, borrador)


def _cargar_datos(espacio):
    """cargarDatos(espacio): copia del espacio guardado para editarla en la sesión."""
    try:
        tarifa = espacio.tarifa
    except Tarifa.DoesNotExist:
        tarifa = None
    horarios = [
        _horario_a_sesion(horario, horario.disponible)
        for horario in espacio.horarios.order_by('id')
    ]
    borrador = {
        'id_espacio': espacio.pk,
        'datos_generales': {
            'nombre': espacio.nombre,
            'descripcion': espacio.descripcion,
            'capacidad': espacio.capacidad,
            'direccion': espacio.direccion,
            'dimensiones_m2': str(espacio.dimensiones_m2) if espacio.dimensiones_m2 is not None else None,
        },
        'fotografias': [
            {'id': foto.pk, 'nombre_archivo': foto.nombre_archivo, 'ruta': foto.archivo.name, 'formato': foto.formato}
            for foto in espacio.fotografias.order_by('id')
        ],
        'horarios': horarios,
        # Lo guardado ya se sincronizó al publicar: solo hay que volver a hacerlo si cambia.
        'calendario_sincronizado': bool(tarifa and horarios),
    }
    if tarifa:
        borrador['tarifa'] = {'precio': str(tarifa.precio), 'periodo': tarifa.periodo}
    return borrador


def _datos_generales(borrador):
    datos = dict(borrador['datos_generales'])
    if datos.get('dimensiones_m2') is not None:
        datos['dimensiones_m2'] = Decimal(datos['dimensiones_m2'])
    return datos


def _espacio_de_borrador(espacio, borrador):
    """Arma los objetos (sin guardar) con los cambios capturados."""
    espacio.aplicar_cambios(_datos_generales(borrador))
    tarifa = Tarifa(precio=Decimal(borrador['tarifa']['precio']), periodo=borrador['tarifa']['periodo'])
    horarios = [_horario_de_sesion(h) for h in borrador['horarios']]
    return espacio, tarifa, horarios


def _mismos_datos(borrador, capturado):
    """True si el precio y los horarios capturados son los del borrador (sin contar ocupados)."""
    anterior = borrador.get('tarifa')
    if not anterior or Decimal(anterior['precio']) != Decimal(capturado['tarifa']['precio']):
        return False
    if anterior['periodo'] != capturado['tarifa']['periodo']:
        return False
    return [{**h, 'ocupado': False} for h in borrador.get('horarios', [])] == capturado['horarios']


def _contexto_pantalla(id_espacio, **extra):
    return {
        'titulo_caso': TITULO_CASO,
        'url_cancelar': reverse('espacios:cancelar_edicion', args=[id_espacio]),
        **extra,
    }


# --- Pantallas --------------------------------------------------------------

@require_GET
@espacio_editable
def abrir_edicion(request, id_espacio):
    """editarEspacios() -> abrirEdicion(): carga los datos del espacio y abre el paso 1."""
    _descartar(request)  # una edición anterior sin terminar se descarta
    _guardar_borrador(request, _cargar_datos(request.espacio))
    return redirect('espacios:editar_informacion', id_espacio=id_espacio)


@require_http_methods(['GET', 'POST'])
@espacio_editable
def editar_informacion(request, id_espacio):
    """FormularioEspacioIH (paso 1): información general, dimensiones y fotografías."""
    borrador = _borrador(request, id_espacio)
    if borrador is None:
        return redirect('espacios:abrir_edicion', id_espacio=id_espacio)
    fotos = borrador['fotografias']
    error_general = None

    if request.method == 'POST' and 'quitar_fotografia' in request.POST:
        indice = int(request.POST['quitar_fotografia'])
        if 0 <= indice < len(fotos):
            # Las fotografías guardadas se borran hasta «Guardar cambios»; las nuevas, ya.
            servicio.descartar_temporales([fotos.pop(indice)])
            _guardar_borrador(request, borrador)
        form = FormularioEdicionEspacio(initial=request.POST.dict(), fotografias_previas=len(fotos))
    elif request.method == 'POST':
        form = FormularioEdicionEspacio(request.POST, request.FILES, fotografias_previas=len(fotos))
        valido = form.is_valid()
        nuevas = form.cleaned_data.get('fotografias', []) if 'fotografias' not in form.errors else []
        try:
            for archivo, formato in nuevas:  # agregarFotografia(archivo)
                fotos.append({'id': None, **almacen_imagenes.guardar_temporal(archivo, formato)})
        except almacen_imagenes.ErrorAlmacenamiento:
            error_general = MENSAJE_FALLA_IMAGENES  # E3
            valido = False
        if valido:
            errores = servicio.revisar_disponibilidad(request.espacio, {'capacidad': form.cleaned_data['capacidad']})
            if errores:
                form.add_error('capacidad', errores['capacidad'])
                valido = False
        if valido:
            borrador['datos_generales'] = form.datos_generales()
            _guardar_borrador(request, borrador)
            return redirect('espacios:editar_precio_y_horarios', id_espacio=id_espacio)  # continuarEditar()
        _guardar_borrador(request, borrador)
    else:
        form = FormularioEdicionEspacio(initial=borrador['datos_generales'], fotografias_previas=len(fotos))

    return render(request, 'espacios/formulario_espacio.html', _contexto_pantalla(
        id_espacio,
        form=form,
        fotografias=[_foto_para_mostrar(f) for f in fotos],
        error_general=error_general,
    ))


@require_http_methods(['GET', 'POST'])
@espacio_editable
def editar_precio_y_horarios(request, id_espacio):
    """PantallaPrecioYHorariosIH (paso 2): precio, modalidad, horarios y sincronización.

    Si el precio y los horarios no cambian se puede continuar sin volver a sincronizar.
    """
    borrador = _borrador(request, id_espacio)
    if borrador is None:
        return redirect('espacios:abrir_edicion', id_espacio=id_espacio)
    empresa = request.empresa
    accion = request.POST.get('accion')
    contexto = {'mostrar_errores': False, 'aviso': None, 'aviso_tipo': None, 'error_modal': None}

    if accion == 'atras':
        return redirect('espacios:editar_informacion', id_espacio=id_espacio)

    if request.method == 'GET':
        form, horarios_form = _formularios_paso_2(borrador)
    elif accion == 'agregar_horario':
        form, horarios_form = _formularios_paso_2(borrador, _agregar_fila(request.POST))
        _invalidar_sincronizacion(request, borrador)
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
            sin_cambios = borrador.get('calendario_sincronizado') and _mismos_datos(borrador, capturado)
            if accion == 'siguiente' and sin_cambios:
                error = _impedimento_para_continuar(request, borrador)
                if error is None:
                    return redirect('espacios:revisar_y_guardar', id_espacio=id_espacio)
                contexto.update(aviso=error, aviso_tipo='error')
            elif accion == 'siguiente':
                borrador.update(capturado)
                _invalidar_sincronizacion(request, borrador)
                contexto.update(aviso=MENSAJE_SINCRONIZACION_PENDIENTE, aviso_tipo='pendiente')
            else:
                # sincronizarCalendario(datos)
                borrador.update(capturado, calendario_sincronizado=False)
                _guardar_borrador(request, borrador)
                contexto.update(_sincronizar(request, borrador, tarifa, horarios))
            form, horarios_form = _formularios_paso_2(borrador)

    sincronizado = borrador.get('calendario_sincronizado', False)
    estados = borrador['horarios'] if sincronizado else [None] * len(horarios_form.forms)
    contexto.update(_contexto_pantalla(
        id_espacio,
        form=form,
        horarios_form=horarios_form,
        filas=list(zip(horarios_form.forms, estados)),
        calendario_vinculado=bool(empresa.id_calendario),
        sincronizado=sincronizado,
        puede_continuar=sincronizado and _hay_horarios_libres(borrador),
    ))
    return render(request, 'espacios/precio_y_horarios.html', contexto)


def _impedimento_para_continuar(request, borrador):
    """«Siguiente» con datos ya sincronizados: revisa horarios libres y reservaciones vigentes.

    Devuelve el mensaje que impide avanzar o None.
    """
    if not _hay_horarios_libres(borrador):
        return servicio.MENSAJES['sin_horarios_libres']
    horarios = [_horario_de_sesion(h) for h in borrador['horarios']]
    return servicio.revisar_disponibilidad(request.espacio, {'horarios': horarios}).get('horarios')


def _sincronizar(request, borrador, tarifa, horarios):
    """Revisa la información y sincroniza con Google Calendar. Devuelve datos para la pantalla."""
    espacio = request.espacio.aplicar_cambios(_datos_generales(borrador))
    errores = servicio.revisar_informacion(espacio, tarifa, horarios, borrador.get('fotografias', []))
    errores.pop('horarios', None)  # los horarios libres se revisan después de sincronizar
    if errores:
        return {'aviso': next(iter(errores.values())), 'aviso_tipo': 'error'}
    if not request.empresa.id_calendario:
        return {}  # la pantalla ofrece «Vincular Google Calendar»
    try:
        en_conflicto = servicio.sincronizar_calendario(request.empresa, horarios)
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
        return {'aviso': servicio.MENSAJES['sin_horarios_libres'], 'aviso_tipo': 'error'}
    if en_conflicto:
        return {'aviso': MENSAJE_CONFLICTO_PARCIAL, 'aviso_tipo': 'pendiente'}
    return {'aviso': MENSAJE_SINCRONIZADO, 'aviso_tipo': 'exito'}


@require_http_methods(['GET', 'POST'])
@espacio_editable
def revisar_y_guardar(request, id_espacio):
    """PantallaRevisarYGuardar (paso 3): mostrarResumen() y guardarCambios()."""
    borrador = _borrador(request, id_espacio)
    if borrador is None:
        return redirect('espacios:abrir_edicion', id_espacio=id_espacio)
    if not borrador.get('calendario_sincronizado') or 'tarifa' not in borrador:
        return redirect('espacios:editar_precio_y_horarios', id_espacio=id_espacio)

    espacio, tarifa, horarios = _espacio_de_borrador(request.espacio, borrador)
    fotos = borrador['fotografias']
    errores = {}
    error_modal = None

    if request.method == 'POST':
        try:
            servicio.actualizar_espacio(
                request.empresa, id_espacio, _datos_generales(borrador), tarifa, horarios, fotos,
            )
        except servicio.EdicionInvalida as error:
            errores = error.errores  # revalidar(): por ejemplo, una reservación nueva
        except servicio.EspacioNoEditable:
            _descartar(request)
            return redirect('espacios:mis_espacios')
        except almacen_imagenes.ErrorAlmacenamiento:
            error_modal = MENSAJE_FALLA_IMAGENES  # E3
        except DatabaseError:
            error_modal = MENSAJE_FALLA_GUARDAR  # E2
        else:
            del request.session[SESION_EDICION]
            return redirect('espacios:espacio_actualizado', id_espacio=id_espacio)

    return render(request, 'espacios/revisar_y_guardar.html', {
        'espacio': espacio,
        'tarifa': tarifa,
        'horarios': horarios,
        'fotografias': [_foto_para_mostrar(f) for f in fotos],
        'empresa': request.empresa,
        'reservaciones_vigentes': len(servicio.buscar_vigentes(espacio)),
        'errores': errores,
        'error_modal': error_modal,
        'url_cancelar': reverse('espacios:cancelar_edicion', args=[id_espacio]),
    })


@require_GET
@espacio_editable
def espacio_actualizado(request, id_espacio):
    """mostrarMensaje(): confirmación de los cambios y volverAMisEspacios()."""
    return render(request, 'espacios/espacio_actualizado.html', {
        'espacio': request.espacio,
        'mensaje': MENSAJE_ACTUALIZADO,
    })


@require_POST
@empresa_requerida
def cancelar_edicion(request, id_espacio):
    """cancelar(): descarta los cambios; el espacio guardado no se modifica."""
    _descartar(request)
    return redirect('espacios:mis_espacios')
