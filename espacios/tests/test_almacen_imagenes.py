"""Pruebas de AlmacenDeImagenes."""
import shutil
import tempfile
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from espacios.servicios import almacen_imagenes as almacen

MEDIA_PRUEBAS = tempfile.mkdtemp()


def archivo(nombre='sala.jpg'):
    return SimpleUploadedFile(nombre, b'contenido de prueba', content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class AlmacenDeImagenesTests(SimpleTestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)
        super().tearDownClass()

    def test_guardar_temporal(self):
        temporal = almacen.guardar_temporal(archivo(), 'JPEG')
        self.assertEqual(temporal['nombre_archivo'], 'sala.jpg')
        self.assertTrue(temporal['ruta'].startswith(almacen.CARPETA_TEMPORAL))
        self.assertTrue(default_storage.exists(temporal['ruta']))

    def test_guardar_fotografias_copia_a_definitiva(self):
        temporal = almacen.guardar_temporal(archivo(), 'JPEG')
        [guardada] = almacen.guardar_fotografias([temporal])
        self.assertTrue(guardada['ruta'].startswith(almacen.CARPETA_DEFINITIVA))
        self.assertTrue(default_storage.exists(guardada['ruta']))
        self.assertTrue(default_storage.exists(temporal['ruta']))  # se descarta después

    def test_falla_al_guardar_temporal(self):
        with mock.patch.object(default_storage, 'save', side_effect=OSError('disco lleno')):
            with self.assertRaises(almacen.ErrorAlmacenamiento):
                almacen.guardar_temporal(archivo(), 'JPEG')

    def test_falla_definitiva_no_deja_imagenes_a_medias(self):
        t1 = almacen.guardar_temporal(archivo('a.jpg'), 'JPEG')
        t2 = almacen.guardar_temporal(archivo('b.jpg'), 'JPEG')
        guardar_original = default_storage.save
        llamadas = []

        def save_que_falla_la_segunda(nombre, contenido, **kwargs):
            llamadas.append(nombre)
            if len(llamadas) == 2:
                raise OSError('falla')
            return guardar_original(nombre, contenido, **kwargs)

        with mock.patch.object(default_storage, 'save', side_effect=save_que_falla_la_segunda):
            with self.assertRaises(almacen.ErrorAlmacenamiento):
                almacen.guardar_fotografias([t1, t2])
        self.assertFalse(default_storage.exists(llamadas[0]))  # la primera se revirtió
        self.assertTrue(default_storage.exists(t1['ruta']))  # las temporales se conservan

    def test_descartar_temporales(self):
        temporal = almacen.guardar_temporal(archivo(), 'PNG')
        almacen.descartar_temporales([temporal])
        self.assertFalse(default_storage.exists(temporal['ruta']))
