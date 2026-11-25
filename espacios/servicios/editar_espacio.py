"""EditarEspacioServicio: reglas y actualización del caso de uso Editar espacio

En el diagrama de clases aparece como EditarEspacioController (capa controlador) y como
el atributo `servicio: EditarEspacioServicio` de EspacioControllerEditarEspacio; son la
misma clase y está aquí (igual que PublicarEspacioService en publicar_espacio.py)

Correspondencia con el diagrama de clases:
- revisarInformacion(datos)                      -> revisar_informacion(...)
- revisarDisponibilidad(espacio, datos)          -> revisar_disponibilidad(espacio, datos)
- validarCompatibilidad(datos, reservas)         -> validar_compatibilidad(datos, reservas)
- revalidar(espacio, datos)                      -> revalidar(...)
- actualizarEspacio(idEmpresa, idEspacio, datos) -> actualizar_espacio(...)
- guardarFotografias(nuevas)                     -> guardar_fotografias(nuevas)
- descartarTemporales()                          -> descartar_temporales(fotografias)
- EspacioRepositorio.buscarPorEmpresa / buscarEspacio / actualizarAtomico
      -> buscar_por_empresa / buscar_espacio / ORM dentro de transaction.atomic()
- ReservacionRepositorio.buscarVigentes(idEspacio) -> buscar_vigentes(espacio)
- ConexionBD -> ORM de Django
"""
import logging

from django.db import transaction
from django.utils import timezone

from espacios.models import Espacio, Fotografia, HorarioDisponible, Reservacion, Tarifa
from espacios.servicios import almacen_imagenes
from espacios.servicios import publicar_espacio

logger = logging.getLogger(__name__)

# Los flujos de Publicar espacio aplican igual al editar; se agregan los de reservaciones
MENSAJES = {
    **publicar_espacio.MENSAJES,
    'capacidad_reservaciones': (
        'La capacidad no puede ser menor a %d personas: hay reservaciones vigentes para esa cantidad'
    ),
    'horarios_reservaciones': (
        'Hay reservaciones vigentes fuera de los horarios disponibles (%s). '
        'Conserve esos horarios para poder guardar los cambios'
    ),
}


class EspacioNoEncontrado(Exception):
    """El espacio no existe o no pertenece a la Empresa (perteneceA)"""


class EspacioNoEditable(Exception):
    """El espacio ya no está publicado (estaDisponible)"""


class EdicionInvalida(Exception):
    """Los cambios no pasaron la revisión y `errores` es {campo: mensaje}"""

    def __init__(self, errores):
        super().__init__(errores)
        self.errores = errores


# --- Repositorios (ORM) -------------------------------------------------------

def buscar_por_empresa(empresa):
    """listarMisEspacios(idEmpresa)"""
    return (
        Espacio.objects.filter(empresa=empresa)
        .select_related('tarifa').prefetch_related('fotografias').order_by('-id')
    )


def buscar_espacio(empresa, id_espacio, bloquear=False):
    """abrirEdicion(idEmpresa, idEspacio): el espacio, solo si es de la Empresa y sigue publicado

    Con `bloquear=True` (dentro de una transacción) bloquea la fila mientras se actualiza
    """
    consulta = Espacio.objects.select_for_update() if bloquear else Espacio.objects.select_related('tarifa')
    espacio = consulta.filter(pk=id_espacio).first()
    if espacio is None or not espacio.pertenece_a(empresa):
        raise EspacioNoEncontrado()
    if not espacio.esta_disponible():
        raise EspacioNoEditable()
    return espacio


def buscar_vigentes(espacio, ahora=None):
    """ReservacionRepositorio.buscarVigentes(idEspacio)"""
    ahora = ahora or timezone.now()
    reservaciones = Reservacion.objects.filter(
        espacio=espacio, estado__in=Reservacion.ESTADOS_VIGENTES, fin__gt=ahora,
    )
    return [reservacion for reservacion in reservaciones if reservacion.es_vigente(ahora)]


# --- Revisión -----------------------------------------------------------------

def revisar_informacion(espacio, tarifa, horarios, fotografias):
    """Mismas reglas que al publicar (A1 a A5). Devuelve {campo: mensaje}"""
    return publicar_espacio.revisar_informacion(espacio, tarifa, horarios, fotografias)


def validar_compatibilidad(datos, reservas):
    """Revisa que las reservaciones sigan cabiendo en los datos editados

    `datos` es un dict con `capacidad` y/o `horarios`; la parte que no venga no se revisa
    (en el paso 1 solo se conoce la capacidad). Devuelve {campo: mensaje}
    """
    errores = {}
    incompatibles = [reserva for reserva in reservas if not reserva.es_compatible_con(datos)]
    if datos.get('capacidad') is not None:
        excedidas = [r for r in incompatibles if r.cantidad_personas > datos['capacidad']]
        if excedidas:
            maximo = max(r.cantidad_personas for r in excedidas)
            errores['capacidad'] = MENSAJES['capacidad_reservaciones'] % maximo
    if datos.get('horarios') is not None:
        fuera = [r for r in incompatibles if not r.cabe_en_horarios(datos['horarios'])]
        if fuera:
            errores['horarios'] = MENSAJES['horarios_reservaciones'] % ', '.join(str(r) for r in fuera)
    return errores


def revisar_disponibilidad(espacio, datos, ahora=None):
    """Compara los datos editados con las reservaciones vigentes del espacio"""
    return validar_compatibilidad(datos, buscar_vigentes(espacio, ahora))


def sincronizar_calendario(empresa, horarios):
    """sincronizarCalendario(datos): igual que al publicar (Google Calendar de la Empresa)"""
    return publicar_espacio.revisar_horarios(empresa, horarios)


def revalidar(espacio, tarifa, horarios, fotografias):
    """Revisión final, justo antes de guardar y con el espacio bloqueado

    Cubre una reservación creada mientras la Empresa editaba
    """
    errores = revisar_informacion(espacio, tarifa, horarios, fotografias)
    for campo, mensaje in revisar_disponibilidad(
        espacio, {'capacidad': espacio.capacidad, 'horarios': horarios},
    ).items():
        errores.setdefault(campo, mensaje)
    return errores


# --- Fotografías --------------------------------------------------------------

def guardar_fotografias(nuevas):
    """Copia las imágenes nuevas a su ubicación definitiva, puede lanzar ErrorAlmacenamiento"""
    return almacen_imagenes.guardar_fotografias(nuevas)


def fotografias_nuevas(fotografias):
    """Las que se agregaron durante la edición (todavía temporales, sin `id`)"""
    return [foto for foto in fotografias if not foto.get('id')]


def descartar_temporales(fotografias):
    """Borra solo las temporales; las fotografías ya guardadas nunca se tocan aquí"""
    almacen_imagenes.descartar_temporales(fotografias_nuevas(fotografias))


# --- Actualización ------------------------------------------------------------

def actualizar_espacio(empresa, id_espacio, datos, tarifa, horarios, fotografias):
    """Guarda los cambios del espacio (actualizarAtomico)

    `datos`: información general (dict de aplicar_cambios). `tarifa`: Tarifa sin guardar.
    `horarios`: HorarioDisponible sin guardar (reemplazan a los anteriores).
    `fotografias`: lista de dicts; las que traen `id` se conservan, las que no son nuevas
    (temporales) y las fotografías guardadas que no aparezcan se eliminan.

    Todo se guarda en una sola transacción: si algo falla no queda nada a medias, se
    borran las copias nuevas y se relanza el error (EdicionInvalida, ErrorAlmacenamiento
    o DatabaseError). Los archivos quitados y las temporales se borran hasta confirmar
    """
    nuevas = fotografias_nuevas(fotografias)
    conservadas = {foto['id'] for foto in fotografias if foto.get('id')}
    guardadas = guardar_fotografias(nuevas)
    try:
        with transaction.atomic():
            espacio = buscar_espacio(empresa, id_espacio, bloquear=True)
            espacio.aplicar_cambios(datos)
            errores = revalidar(espacio, tarifa, horarios, fotografias)
            if errores:
                raise EdicionInvalida(errores)
            espacio.save()
            Tarifa.objects.update_or_create(
                espacio=espacio, defaults={'precio': tarifa.precio, 'periodo': tarifa.periodo},
            )
            espacio.horarios.all().delete()
            for horario in horarios:
                horario.pk = None
                horario.espacio = espacio
            HorarioDisponible.objects.bulk_create(horarios)
            quitadas = list(espacio.fotografias.exclude(pk__in=conservadas))
            Fotografia.objects.filter(pk__in=[foto.pk for foto in quitadas]).delete()
            Fotografia.objects.bulk_create([
                Fotografia(
                    espacio=espacio, nombre_archivo=foto['nombre_archivo'],
                    archivo=foto['ruta'], formato=foto['formato'],
                )
                for foto in guardadas
            ])
    except EdicionInvalida:
        almacen_imagenes.eliminar_fotografias([foto['ruta'] for foto in guardadas])
        raise
    except Exception:
        logger.exception('Falló la actualización del espacio %s; se revierte la operación', id_espacio)
        almacen_imagenes.eliminar_fotografias([foto['ruta'] for foto in guardadas])
        raise
    almacen_imagenes.eliminar_fotografias([foto.archivo.name for foto in quitadas])
    almacen_imagenes.descartar_temporales(nuevas)
    return espacio
