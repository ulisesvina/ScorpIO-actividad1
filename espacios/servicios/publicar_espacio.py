"""PublicarEspacioService: reglas y registro del caso de uso Publicar espacio

Correspondencia con el diagrama de clases y el de secuencia:
- revisarInformacion(espacio) -> revisar_informacion(...)
- revisarHorarios(horarios)   -> revisar_horarios(...)
- guardarFotografias()        -> guardar_fotografias(...)
- crearEspacio(espacio)       -> crear_espacio(...)
EspacioBD.guardarEspacio() y ConexionBD -> ORM dentro de transaction.atomic()
"""
import logging

from django.db import transaction

from espacios.models import Fotografia, HorarioDisponible
from espacios.servicios import almacen_imagenes, google_calendar

logger = logging.getLogger(__name__)

# Mensajes de los flujos alternativos
MENSAJES = {
    'nombre': 'Ingrese el nombre del espacio',
    'descripcion': 'Ingrese una descripción del espacio',
    'capacidad': 'La capacidad debe ser mayor que cero',
    'direccion': 'Ingrese la ubicación del espacio',
    'fotografias': 'Agregue al menos una fotografía',
    'formato_fotografias': 'No fue posible agregar una o más imágenes. Verifique el formato de los archivos',
    'precio': 'El precio debe ser mayor que cero',
    'periodo': 'Seleccione un periodo de reservación',
    'horarios': 'Verifique los horarios ingresados',
    'sin_horarios_libres': 'No quedan horarios disponibles. Registre otros horarios antes de continuar',
}


class PublicacionInvalida(Exception):
    """La información no pasó la revisión y  `errores` es {campo: mensaje}"""

    def __init__(self, errores):
        super().__init__(errores)
        self.errores = errores


def _revisar_horarios_capturados(horarios):
    if not horarios:
        return False
    if any(not horario.es_valido() for horario in horarios):
        return False
    for i, horario in enumerate(horarios):
        for otro in horarios[i + 1:]:
            if horario.se_superpone_con(otro):  # repetidos o encimados
                return False
    return True


def revisar_informacion(espacio, tarifa, horarios, fotografias):
    """checa que los datos estén completos y sean válidos

    `fotografias` es la lista de dicts de AlmacenDeImagenes. Devuelve {campo: mensaje};
    vacío si todo es correcto
    """
    errores = {}
    for campo in ('nombre', 'descripcion', 'direccion'):
        if not (getattr(espacio, campo) or '').strip():
            errores[campo] = MENSAJES[campo]
    if not espacio.capacidad or espacio.capacidad <= 0:
        errores['capacidad'] = MENSAJES['capacidad']

    if not fotografias:
        errores['fotografias'] = MENSAJES['fotografias']
    elif any(not Fotografia(formato=foto['formato']).es_valida() for foto in fotografias):
        errores['fotografias'] = MENSAJES['formato_fotografias']

    if tarifa.precio is None or tarifa.precio <= 0:
        errores['precio'] = MENSAJES['precio']
    if not tarifa.es_valida() and 'precio' not in errores:
        errores['periodo'] = MENSAJES['periodo']

    if not _revisar_horarios_capturados(horarios):
        errores['horarios'] = MENSAJES['horarios']
    elif not any(horario.disponible for horario in horarios):
        errores['horarios'] = MENSAJES['sin_horarios_libres']
    return errores


def revisar_horarios(empresa, horarios):
    """Sincroniza con el Google Calendar de la Empresa y marca los horarios ocupados 

    Devuelve la lista de horarios en conflicto. Lanza google_calendar.CalendarioNoDisponible
    o google_calendar.CalendarioSinAcceso si la Empresa no tiene calendario vinculado
    """
    if not empresa.id_calendario:
        raise google_calendar.CalendarioSinAcceso()
    return google_calendar.revisar_horarios(empresa.id_calendario, horarios)


def guardar_fotografias(fotografias):
    """Guarda las imágenes en su ubicación definitiva, puede lanzar ErrorAlmacenamiento"""
    return almacen_imagenes.guardar_fotografias(fotografias)


def crear_espacio(espacio, tarifa, horarios, fotografias):
    """Registra el espacio ya publicado con su tarifa, horarios y fotografías

    Todo se guarda en una sola transacción: si la base de datos falla no queda
    ningún registro incompleto, se borran las imágenes copiadas y se relanza el error
    Las imágenes temporales se conservan hasta que el registro se confirma
    """
    guardadas = guardar_fotografias(fotografias)
    try:
        with transaction.atomic():
            espacio.save()
            tarifa.espacio = espacio
            tarifa.save()
            for horario in horarios:
                horario.espacio = espacio
            HorarioDisponible.objects.bulk_create(horarios)
            Fotografia.objects.bulk_create([
                Fotografia(
                    espacio=espacio, nombre_archivo=foto['nombre_archivo'],
                    archivo=foto['ruta'], formato=foto['formato'],
                )
                for foto in guardadas
            ])
    except Exception:
        logger.exception('Falló el registro del espacio; se revierte la operación')
        espacio.pk = None
        tarifa.pk = None
        almacen_imagenes.eliminar_fotografias([foto['ruta'] for foto in guardadas])
        raise
    almacen_imagenes.descartar_temporales(fotografias)
    return espacio
