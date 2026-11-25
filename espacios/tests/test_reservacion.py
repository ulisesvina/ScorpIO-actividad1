"""Pruebas de las reglas de los modelos agregadas por Editar espacio (Reservacion y Espacio)"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from espacios.models import Espacio, HorarioDisponible, Reservacion
from espacios.tests.test_modelos import DATOS_GENERALES, crear_empresa

# Lunes 2 de noviembre de 2026, dentro del periodo de reservaciones
LUNES = datetime(2026, 11, 2)


def en_lunes(hora_inicio, hora_fin, dias=0):
    zona = timezone.get_current_timezone()
    fecha = LUNES + timedelta(days=dias)
    return (
        timezone.make_aware(datetime.combine(fecha, hora_inicio), zona),
        timezone.make_aware(datetime.combine(fecha, hora_fin), zona),
    )


def horario(dia='lunes', inicio=9, fin=18, disponible=True):
    return HorarioDisponible(dia=dia, hora_inicio=time(inicio), hora_fin=time(fin), disponible=disponible)


class ReservacionTests(TestCase):
    def setUp(self):
        inicio, fin = en_lunes(time(10), time(12))
        self.reservacion = Reservacion(inicio=inicio, fin=fin, cantidad_personas=8, estado=Reservacion.CONFIRMADA)
        self.antes = inicio - timedelta(days=1)

    def test_es_vigente_si_no_ha_terminado(self):
        self.assertTrue(self.reservacion.es_vigente(self.antes))
        self.assertFalse(self.reservacion.es_vigente(self.reservacion.fin + timedelta(minutes=1)))

    def test_cancelada_o_finalizada_no_es_vigente(self):
        for estado in (Reservacion.CANCELADA, Reservacion.FINALIZADA):
            self.reservacion.estado = estado
            self.assertFalse(self.reservacion.es_vigente(self.antes))

    def test_pendiente_es_vigente(self):
        self.reservacion.estado = Reservacion.PENDIENTE
        self.assertTrue(self.reservacion.es_vigente(self.antes))

    def test_compatible_dentro_de_capacidad_y_horario(self):
        self.assertTrue(self.reservacion.es_compatible_con({'capacidad': 8, 'horarios': [horario()]}))

    def test_incompatible_por_capacidad(self):
        self.assertFalse(self.reservacion.es_compatible_con({'capacidad': 7, 'horarios': [horario()]}))

    def test_incompatible_si_el_horario_no_la_cubre(self):
        self.assertFalse(self.reservacion.es_compatible_con({'capacidad': 10, 'horarios': [horario(inicio=11)]}))
        self.assertFalse(self.reservacion.es_compatible_con({'capacidad': 10, 'horarios': [horario('martes')]}))

    def test_incompatible_si_el_horario_esta_desactivado(self):
        datos = {'capacidad': 10, 'horarios': [horario(disponible=False)]}
        self.assertFalse(self.reservacion.es_compatible_con(datos))

    def test_solo_revisa_lo_que_se_indica(self):
        self.assertTrue(self.reservacion.es_compatible_con({'capacidad': 8}))
        self.assertFalse(self.reservacion.es_compatible_con({'capacidad': 2}))
        self.assertTrue(self.reservacion.es_compatible_con({'horarios': [horario()]}))

    def test_reservacion_de_varios_dias_no_cabe(self):
        inicio, _ = en_lunes(time(10), time(12))
        _, fin = en_lunes(time(10), time(12), dias=1)
        reservacion = Reservacion(inicio=inicio, fin=fin, cantidad_personas=1)
        self.assertFalse(reservacion.cabe_en_horarios([horario(inicio=0, fin=23)]))

    def test_texto(self):
        self.assertEqual(str(self.reservacion), '02/11/2026 10:00–12:00')


class EspacioEdicionTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa()
        self.espacio = Espacio.objects.create(
            empresa=self.empresa, estado=Espacio.PUBLICADO, **DATOS_GENERALES,
        )

    def test_pertenece_a(self):
        self.assertTrue(self.espacio.pertenece_a(self.empresa))
        self.assertFalse(self.espacio.pertenece_a(None))

    def test_esta_disponible_si_esta_publicado(self):
        self.assertTrue(self.espacio.esta_disponible())
        self.espacio.estado = ''
        self.assertFalse(self.espacio.esta_disponible())

    def test_aplicar_cambios_no_cambia_id_ni_empresa(self):
        id_original = self.espacio.pk
        self.espacio.aplicar_cambios({**DATOS_GENERALES, 'nombre': 'Nuevo', 'dimensiones_m2': Decimal('45.5')})
        self.assertEqual(self.espacio.nombre, 'Nuevo')
        self.assertEqual(self.espacio.dimensiones_m2, Decimal('45.5'))
        self.assertEqual(self.espacio.pk, id_original)
        self.assertEqual(self.espacio.empresa, self.empresa)

    def test_aplicar_cambios_sin_dimensiones(self):
        self.espacio.dimensiones_m2 = Decimal('10')
        self.espacio.aplicar_cambios(DATOS_GENERALES)
        self.assertIsNone(self.espacio.dimensiones_m2)
