"""GoogleCalendarService: consulta la disponibilidad del Google Calendar de una Empresa

La Empresa comparte su calendario con la cuenta de servicio de Reserva-Hub (permiso
"Ver solo información de disponible/ocupado") y registra su ID de calendario
(`Empresa.id_calendario`). La sincronización es manual (botón) y de solo lectura

Correspondencia con los diagramas:(para qno haya incoherencias)
- revisarHorarios()                -> revisar_horarios(id_calendario, horarios)
- consultarEventos(idCal, rango)   -> consultar_eventos(id_calendario, inicio, fin)
"""
import json
import logging
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

ALCANCES = ['https://www.googleapis.com/auth/calendar.readonly']
SEGUNDOS_DE_ESPERA = 10

# Fechas en que se pueden reservar los espacios (acordado por nosotros)
PRIMER_DIA = date(2026, 11, 1)
ULTIMO_DIA = date(2026, 12, 31)

NUMERO_DE_DIA = {
    'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
    'viernes': 4, 'sabado': 5, 'domingo': 6,
}


class CalendarioNoDisponible(Exception):
    """Google Calendar no respondió o no está configurado"""


class CalendarioSinAcceso(Exception):
    """El calendario no existe o no está compartido con la cuenta de servicio"""


def correo_cuenta_de_servicio():
    """Correo con el que la Empresa debe compartir su calendario ('' si no hay llave)"""
    ruta = settings.GOOGLE_CALENDAR_CREDENCIALES
    if not ruta:
        return ''
    try:
        with open(ruta, encoding='utf-8') as archivo:
            return json.load(archivo).get('client_email', '')
    except (OSError, ValueError):
        logger.exception('No se pudo leer la llave de Google Calendar')
        return ''


def _cliente():
    """Construye el cliente de la API de Google Calendar"""
    # Importación local: el resto del proyecto no depende de las librerías de Google
    import google_auth_httplib2
    import httplib2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credenciales = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_CALENDAR_CREDENCIALES, scopes=ALCANCES,
    )
    http = google_auth_httplib2.AuthorizedHttp(credenciales, http=httplib2.Http(timeout=SEGUNDOS_DE_ESPERA))
    return build('calendar', 'v3', http=http, cache_discovery=False)


def consultar_eventos(id_calendario, inicio, fin):
    """regresa los intervalos ocupados [(inicio, fin), ...] del calendario entre dos fechas"""
    if not settings.GOOGLE_CALENDAR_CREDENCIALES:
        logger.error('GOOGLE_CALENDAR_CREDENCIALES no está definida')
        raise CalendarioNoDisponible()
    try:
        respuesta = _cliente().freebusy().query(body={
            'timeMin': inicio.isoformat(),
            'timeMax': fin.isoformat(),
            'timeZone': settings.TIME_ZONE,
            'items': [{'id': id_calendario}],
        }).execute()
    except Exception as error:  # red, tiempo de espera, HttpError, llave inválida...
        logger.exception('Google Calendar no respondió')
        raise CalendarioNoDisponible() from error

    calendario = respuesta.get('calendars', {}).get(id_calendario, {})
    if calendario.get('errors') or id_calendario not in respuesta.get('calendars', {}):
        logger.warning('Sin acceso al calendario %s: %s', id_calendario, calendario.get('errors'))
        raise CalendarioSinAcceso()
    return [
        (parse_datetime(ocupado['start']), parse_datetime(ocupado['end']))
        for ocupado in calendario.get('busy', [])
    ]


def rango_de_consulta(ahora=None):
    """periodo a revisar: desde hoy (o el primer día) hasta el fin del último día"""
    ahora = timezone.localtime(ahora or timezone.now())
    desde = max(ahora.date(), PRIMER_DIA)
    zona = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), zona)
    fin = timezone.make_aware(datetime.combine(ULTIMO_DIA + timedelta(days=1), time.min), zona)
    return inicio, fin


def _ocurrencias(horario, inicio, fin):
    """intervalos concretos de un horario semanal dentro del periodo"""
    zona = timezone.get_current_timezone()
    dia = inicio.date()
    while dia < fin.date():
        if dia.weekday() == NUMERO_DE_DIA[horario.dia]:
            yield (
                timezone.make_aware(datetime.combine(dia, horario.hora_inicio), zona),
                timezone.make_aware(datetime.combine(dia, horario.hora_fin), zona),
            )
        dia += timedelta(days=1)


def revisar_horarios(id_calendario, horarios, ahora=None):
    """marca como no disponibles los horarios ocupados en Google Calendar 

    `horarios` son instancias de HorarioDisponible (sin guardar). Un horario semanal
    queda ocupado si cualquiera de sus fechas dentro del periodo choca con un evento
    Los horarios que la Empresa ya desactivó no se revisan
    Devuelve la lista de horarios que resultaron ocupados
    """
    inicio, fin = rango_de_consulta(ahora)
    if inicio >= fin:
        return []
    ocupados = consultar_eventos(id_calendario, inicio, fin)
    en_conflicto = []
    for horario in horarios:
        if not horario.disponible:
            continue
        for desde, hasta in _ocurrencias(horario, inicio, fin):
            if any(desde < fin_evento and inicio_evento < hasta for inicio_evento, fin_evento in ocupados):
                horario.disponible = False
                en_conflicto.append(horario)
                break
    return en_conflicto
