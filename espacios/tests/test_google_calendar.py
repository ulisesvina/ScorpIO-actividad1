"""Pruebas de GoogleCalendarService (sin conectarse a Google: el cliente se simula)"""
from datetime import datetime, time
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from espacios.models import HorarioDisponible
from espacios.servicios import google_calendar as calendario

ID_CALENDARIO = 'clinica@ejemplo.com'
# Miércoles 18 de noviembre de 2026, 10:00 en la Ciudad de México
AHORA = timezone.make_aware(datetime(2026, 11, 18, 10, 0))


def cliente_con(respuesta=None, error=None):
    """cliente falso cuya consulta freebusy devuelve `respuesta` o lanza `error`"""
    cliente = mock.Mock()
    consulta = cliente.freebusy.return_value.query.return_value
    if error:
        consulta.execute.side_effect = error
    else:
        consulta.execute.return_value = respuesta
    return cliente


def ocupado(inicio, fin):
    return {'calendars': {ID_CALENDARIO: {'busy': [{'start': inicio, 'end': fin}]}}}


def horario(dia, inicio=9, fin=18, disponible=True):
    return HorarioDisponible(dia=dia, hora_inicio=time(inicio), hora_fin=time(fin), disponible=disponible)


@override_settings(GOOGLE_CALENDAR_CREDENCIALES='/ruta/llave.json')
class RevisarHorariosTests(SimpleTestCase):
    def revisar(self, horarios, respuesta=None, error=None):
        with mock.patch.object(calendario, '_cliente', return_value=cliente_con(respuesta, error)):
            return calendario.revisar_horarios(ID_CALENDARIO, horarios, ahora=AHORA)

    def test_conflicto_parcial_a9(self):
        # Lunes 23 de noviembre ocupado de 10 a 12: el lunes queda ocupado, el martes libre.
        lunes, martes = horario('lunes'), horario('martes')
        en_conflicto = self.revisar(
            [lunes, martes], ocupado('2026-11-23T10:00:00-06:00', '2026-11-23T12:00:00-06:00'),
        )
        self.assertEqual(en_conflicto, [lunes])
        self.assertFalse(lunes.disponible)
        self.assertTrue(martes.disponible)

    def test_sin_eventos_todo_disponible(self):
        lunes = horario('lunes')
        self.assertEqual(self.revisar([lunes], {'calendars': {ID_CALENDARIO: {'busy': []}}}), [])
        self.assertTrue(lunes.disponible)

    def test_evento_fuera_del_horario_no_choca(self):
        lunes = horario('lunes', 9, 18)
        self.revisar([lunes], ocupado('2026-11-23T18:00:00-06:00', '2026-11-23T20:00:00-06:00'))
        self.assertTrue(lunes.disponible)

    def test_horario_desactivado_por_la_empresa_no_se_revisa(self):
        miercoles = horario('miercoles', disponible=False)
        self.assertEqual(
            self.revisar([miercoles], ocupado('2026-11-25T10:00:00-06:00', '2026-11-25T11:00:00-06:00')), [],
        )

    def test_fechas_pasadas_no_cuentan(self):
        # Lunes 16 de noviembre ya pasó (hoy es 18).
        lunes = horario('lunes')
        self.revisar([lunes], ocupado('2026-11-16T10:00:00-06:00', '2026-11-16T12:00:00-06:00'))
        self.assertTrue(lunes.disponible)

    def test_google_no_responde_e1(self):
        with self.assertRaises(calendario.CalendarioNoDisponible):
            self.revisar([horario('lunes')], error=OSError('sin red'))

    def test_calendario_no_compartido(self):
        respuesta = {'calendars': {ID_CALENDARIO: {'errors': [{'reason': 'notFound'}], 'busy': []}}}
        with self.assertRaises(calendario.CalendarioSinAcceso):
            self.revisar([horario('lunes')], respuesta)

    @override_settings(GOOGLE_CALENDAR_CREDENCIALES='')
    def test_sin_llave_configurada_es_e1(self):
        with self.assertRaises(calendario.CalendarioNoDisponible):
            calendario.revisar_horarios(ID_CALENDARIO, [horario('lunes')], ahora=AHORA)


class RangoDeConsultaTests(SimpleTestCase):
    def test_empieza_hoy_y_termina_el_31_de_diciembre(self):
        inicio, fin = calendario.rango_de_consulta(AHORA)
        self.assertEqual(timezone.localtime(inicio).date().isoformat(), '2026-11-18')
        self.assertEqual(timezone.localtime(fin).date().isoformat(), '2027-01-01')

    def test_antes_de_noviembre_empieza_el_1(self):
        inicio, _ = calendario.rango_de_consulta(timezone.make_aware(datetime(2026, 10, 5, 9, 0)))
        self.assertEqual(timezone.localtime(inicio).date().isoformat(), '2026-11-01')
