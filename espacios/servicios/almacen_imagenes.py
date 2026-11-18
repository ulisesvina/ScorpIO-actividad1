"""AlmacenDeImagenes: guarda las fotografías de los espacios en el disco local (MEDIA_ROOT)

Las imágenes se guardan primero en una carpeta temporal para
detectar a tiempo una falla de almacenamiento, luego  al publicar, `guardar_fotografias`
las mueve a su ubicación definitiva 
"""
import logging
import uuid

from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

CARPETA_TEMPORAL = 'espacios/temporales/'
CARPETA_DEFINITIVA = 'espacios/fotografias/'
EXTENSIONES = {'JPEG': '.jpg', 'PNG': '.png'}


class ErrorAlmacenamiento(Exception):
    """No fue posible guardar una o más imágenes"""


def _nombre_unico(carpeta, formato):
    return '%s%s%s' % (carpeta, uuid.uuid4().hex, EXTENSIONES[formato])


def guardar_temporal(archivo, formato):
    """Guarda una imagen ya validada en la carpeta temporal

    Devuelve un dict con nombre_archivo, ruta y formato, q si es valido  para guardarse en la sesion
    """
    try:
        ruta = default_storage.save(_nombre_unico(CARPETA_TEMPORAL, formato), archivo)
    except Exception as error:  # OSError, errores del almacenamiento, etc.
        logger.exception('Falló el guardado temporal de una fotografía')
        raise ErrorAlmacenamiento() from error
    return {'nombre_archivo': archivo.name, 'ruta': ruta, 'formato': formato}


def guardar_fotografias(temporales):
    """Mueve las imágenes temporales a su ubicación definitiva

    Devuelve la lista de dicts con la ruta definitiva. Si alguna falla, elimina las
    que ya se habían movido y lanza ErrorAlmacenamiento
    """
    guardadas = []
    try:
        for temporal in temporales:
            with default_storage.open(temporal['ruta'], 'rb') as origen:
                ruta = default_storage.save(_nombre_unico(CARPETA_DEFINITIVA, temporal['formato']), origen)
            guardadas.append({**temporal, 'ruta': ruta})
    except Exception as error:
        logger.exception('Falló el almacenamiento definitivo de las fotografías')
        eliminar_fotografias([g['ruta'] for g in guardadas])
        raise ErrorAlmacenamiento() from error
    descartar_temporales(temporales)
    return guardadas


def eliminar_fotografias(rutas):
    """Borra imágenes del almacenamiento y no lanza excepciones"""
    for ruta in rutas:
        try:
            default_storage.delete(ruta)
        except Exception:
            logger.exception('No se pudo eliminar la imagen %s', ruta)


def descartar_temporales(temporales):
    """Borra las imágenes temporales (al publicar o al cancelar)"""
    eliminar_fotografias([t['ruta'] for t in temporales])
