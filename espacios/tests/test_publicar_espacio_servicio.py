"""Pruebas de PublicarEspacioService"""
import shutil
import tempfile
from datetime import time
from decimal import Decimal
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase, override_settings

from espacios.models import Espacio, Fotografia, HorarioDisponible, Tarifa
from espacios.servicios import almacen_imagenes
from espacios.servicios import google_calendar
from espacios.servicios import publicar_espacio as servicio
from espacios.tests.test_modelos import DATOS_GENERALES, crear_empresa

MEDIA_PRUEBAS = tempfile.mkdtemp()


def foto_temporal(nombre='sala.jpg'):
    archivo = SimpleUploadedFile(nombre, b'imagen', content_type='image/jpeg')
    return almacen_imagenes.guardar_temporal(archivo, 'JPEG')


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class PublicarEspacioServicioTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.empresa = crear_empresa()
        self.espacio = Espacio().capturar_datos(DATOS_GENERALES, self.empresa)
        self.tarifa = Tarifa(precio=Decimal('350'), periodo=Tarifa.POR_HORA)
        self.horarios = [HorarioDisponible(dia='lunes', hora_inicio=time(9), hora_fin=time(18))]
        self.fotos = [foto_temporal()]

    def revisar(self):
        return servicio.revisar_informacion(self.espacio, self.tarifa, self.horarios, self.fotos)


    def test_datos_validos(self):
        self.assertEqual(self.revisar(), {})

    def test_campos_obligatorios_vacios_a1(self):
        self.espacio.nombre = ''
        self.espacio.descripcion = '   '
        self.espacio.direccion = ''
        errores = self.revisar()
        self.assertEqual(errores['nombre'], 'Ingrese el nombre del espacio')
        self.assertEqual(errores['descripcion'], 'Ingrese una descripción del espacio')
        self.assertEqual(errores['direccion'], 'Ingrese la ubicación del espacio')

    def test_sin_fotografias_a2(self):
        self.fotos = []
        self.assertEqual(self.revisar()['fotografias'], 'Agregue al menos una fotografía')

    def test_capacidad_cero_a3(self):
        self.espacio.capacidad = 0
        self.assertEqual(self.revisar()['capacidad'], 'La capacidad debe ser mayor que cero')

    def test_precio_cero_a3(self):
        self.tarifa.precio = Decimal('0')
        self.assertEqual(self.revisar()['precio'], 'El precio debe ser mayor que cero')

    def test_sin_periodo_a3(self):
        self.tarifa.periodo = ''
        self.assertEqual(self.revisar()['periodo'], 'Seleccione un periodo de reservación')

    def test_sin_horarios_a4(self):
        self.horarios = []
        self.assertEqual(self.revisar()['horarios'], 'Verifique los horarios ingresados')

    def test_hora_final_anterior_a4(self):
        self.horarios = [HorarioDisponible(dia='lunes', hora_inicio=time(18), hora_fin=time(9))]
        self.assertEqual(self.revisar()['horarios'], 'Verifique los horarios ingresados')

    def test_horarios_repetidos_a4(self):
        self.horarios.append(HorarioDisponible(dia='lunes', hora_inicio=time(9), hora_fin=time(18)))
        self.assertEqual(self.revisar()['horarios'], 'Verifique los horarios ingresados')

    def test_ningun_horario_libre_a5(self):
        self.horarios[0].disponible = False
        self.assertEqual(
            self.revisar()['horarios'],
            'No quedan horarios disponibles. Registre otros horarios antes de continuar',
        )

    # revisar_horarios

    def test_revisar_horarios_sin_calendario_vinculado(self):
        with self.assertRaises(google_calendar.CalendarioSinAcceso):
            servicio.revisar_horarios(self.empresa, self.horarios)

    def test_revisar_horarios_usa_el_calendario_de_la_empresa(self):
        self.empresa.id_calendario = 'clinica@ejemplo.com'
        with mock.patch.object(google_calendar, 'revisar_horarios', return_value=[]) as revisar:
            servicio.revisar_horarios(self.empresa, self.horarios)
        revisar.assert_called_once_with('clinica@ejemplo.com', self.horarios)

    # crear_espacio

    def test_crear_espacio_registra_todo(self):
        self.espacio.publicar()
        espacio = servicio.crear_espacio(self.espacio, self.tarifa, self.horarios, self.fotos)
        espacio = Espacio.objects.get(pk=espacio.pk)
        self.assertEqual(espacio.estado, Espacio.PUBLICADO)
        self.assertEqual(espacio.empresa, self.empresa)
        self.assertEqual(espacio.tarifa.precio, Decimal('350'))
        self.assertEqual(espacio.horarios.count(), 1)
        foto = espacio.fotografias.get()
        self.assertTrue(foto.archivo.name.startswith(almacen_imagenes.CARPETA_DEFINITIVA))
        self.assertTrue(default_storage.exists(foto.archivo.name))
        self.assertFalse(default_storage.exists(self.fotos[0]['ruta']))

    def definitivas(self):
        if not default_storage.exists(almacen_imagenes.CARPETA_DEFINITIVA):
            return set()
        return set(default_storage.listdir(almacen_imagenes.CARPETA_DEFINITIVA)[1])

    def test_falla_de_base_de_datos_no_deja_registros_e2(self):
        self.espacio.publicar()
        antes = self.definitivas()
        with mock.patch.object(HorarioDisponible.objects, 'bulk_create', side_effect=DatabaseError('caída')):
            with self.assertRaises(DatabaseError):
                servicio.crear_espacio(self.espacio, self.tarifa, self.horarios, self.fotos)
        self.assertFalse(Espacio.objects.exists())
        self.assertFalse(Tarifa.objects.exists())
        self.assertIsNone(self.espacio.pk)
        self.assertTrue(default_storage.exists(self.fotos[0]['ruta']))  # se conserva para reintentar
        self.assertEqual(self.definitivas(), antes)  # la copia definitiva se borró

    def test_falla_al_guardar_imagenes_no_registra_e3(self):
        self.espacio.publicar()
        with mock.patch.object(
            almacen_imagenes, 'guardar_fotografias', side_effect=almacen_imagenes.ErrorAlmacenamiento(),
        ):
            with self.assertRaises(almacen_imagenes.ErrorAlmacenamiento):
                servicio.crear_espacio(self.espacio, self.tarifa, self.horarios, self.fotos)
        self.assertFalse(Espacio.objects.exists())
        self.assertFalse(Fotografia.objects.exists())
