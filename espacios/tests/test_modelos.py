"""Pruebas de las reglas de los modelos de Publicar espacio"""
from datetime import time
from decimal import Decimal

from django.test import TestCase

from cuentas.models import Empresa, Usuario
from espacios.models import Espacio, Fotografia, HorarioDisponible, Tarifa


def crear_empresa():
    usuario = Usuario.objects.create_user(
        correo='clinica@ejemplo.com', password='Reserva2026-Hub', nombre='Clínica Ejemplo',
        es_empresa=True, is_active=True,
    )
    return Empresa.objects.create(usuario=usuario, rfc='CEJ010203AB1')


DATOS_GENERALES = {
    'nombre': 'Sala de juntas Central',
    'descripcion': 'Espacio equipado para reuniones',
    'capacidad': 10,
    'direccion': 'Av. Reforma 123',
}


class EspacioTests(TestCase):
    def test_capturar_datos_asocia_la_empresa(self):
        empresa = crear_empresa()
        espacio = Espacio().capturar_datos(DATOS_GENERALES, empresa)
        self.assertEqual(espacio.empresa, empresa)
        self.assertEqual(espacio.nombre, 'Sala de juntas Central')
        self.assertIsNone(espacio.pk)  # capturar no guarda

    def test_publicar_cambia_el_estado(self):
        espacio = Espacio().capturar_datos(DATOS_GENERALES, crear_empresa())
        espacio.publicar()
        espacio.save()
        self.assertEqual(Espacio.objects.get().estado, Espacio.PUBLICADO)


class TarifaTests(TestCase):
    def test_precio_mayor_que_cero_y_periodo_valido(self):
        self.assertTrue(Tarifa(precio=Decimal('350'), periodo=Tarifa.POR_HORA).es_valida())

    def test_precio_cero_o_negativo_no_es_valido(self):
        self.assertFalse(Tarifa(precio=Decimal('0'), periodo=Tarifa.POR_HORA).es_valida())
        self.assertFalse(Tarifa(precio=Decimal('-5'), periodo=Tarifa.POR_DIA).es_valida())

    def test_sin_periodo_no_es_valida(self):
        self.assertFalse(Tarifa(precio=Decimal('350'), periodo='').es_valida())


class HorarioDisponibleTests(TestCase):
    def test_hora_final_posterior_es_valida(self):
        self.assertTrue(HorarioDisponible(dia='lunes', hora_inicio=time(9), hora_fin=time(18)).es_valido())

    def test_hora_final_anterior_o_igual_no_es_valida(self):
        self.assertFalse(HorarioDisponible(dia='lunes', hora_inicio=time(18), hora_fin=time(9)).es_valido())
        self.assertFalse(HorarioDisponible(dia='lunes', hora_inicio=time(9), hora_fin=time(9)).es_valido())

    def test_superposicion_mismo_dia(self):
        a = HorarioDisponible(dia='martes', hora_inicio=time(9), hora_fin=time(18))
        b = HorarioDisponible(dia='martes', hora_inicio=time(9), hora_fin=time(18))
        c = HorarioDisponible(dia='martes', hora_inicio=time(17), hora_fin=time(20))
        d = HorarioDisponible(dia='martes', hora_inicio=time(18), hora_fin=time(20))
        self.assertTrue(a.se_superpone_con(b))  # repetido
        self.assertTrue(a.se_superpone_con(c))  # se cruzan
        self.assertFalse(a.se_superpone_con(d))  # contiguos

    def test_dias_distintos_no_se_superponen(self):
        a = HorarioDisponible(dia='lunes', hora_inicio=time(9), hora_fin=time(18))
        b = HorarioDisponible(dia='martes', hora_inicio=time(9), hora_fin=time(18))
        self.assertFalse(a.se_superpone_con(b))


class FotografiaTests(TestCase):
    def test_formatos_permitidos(self):
        self.assertTrue(Fotografia(formato='JPEG').es_valida())
        self.assertTrue(Fotografia(formato='png').es_valida())
        self.assertFalse(Fotografia(formato='GIF').es_valida())
