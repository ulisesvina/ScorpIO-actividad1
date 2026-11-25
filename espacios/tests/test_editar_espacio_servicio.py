"""Pruebas de EditarEspacioServicio"""
import io
import shutil
import tempfile
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from cuentas.models import Empresa, Usuario
from espacios.models import Espacio, Fotografia, HorarioDisponible, Reservacion, Tarifa
from espacios.servicios import almacen_imagenes
from espacios.servicios import editar_espacio as servicio
from espacios.tests.test_modelos import DATOS_GENERALES

MEDIA_PRUEBAS = tempfile.mkdtemp()


def png():
    contenido = io.BytesIO()
    Image.new('RGB', (2, 2)).save(contenido, 'PNG')
    return contenido.getvalue()


def crear_espacio_publicado(empresa, **cambios):
    """Espacio como lo deja Publicar espacio: lunes 09:00–18:00, $350 / hora y una foto."""
    espacio = Espacio.objects.create(empresa=empresa, estado=Espacio.PUBLICADO, **{**DATOS_GENERALES, **cambios})
    Tarifa.objects.create(espacio=espacio, precio=Decimal('350'), periodo=Tarifa.POR_HORA)
    HorarioDisponible.objects.create(espacio=espacio, dia='lunes', hora_inicio=time(9), hora_fin=time(18))
    ruta = default_storage.save('espacios/fotografias/sala.png', ContentFile(png()))
    Fotografia.objects.create(espacio=espacio, nombre_archivo='sala.png', archivo=ruta, formato='PNG')
    return espacio


def proximo_lunes(hora_inicio=time(10), hora_fin=time(12)):
    """Intervalo de un lunes futuro (siempre vigente)."""
    hoy = timezone.localdate()
    fecha = hoy + timedelta(days=(7 - hoy.weekday()) or 7)
    zona = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(fecha, hora_inicio), zona),
        timezone.make_aware(datetime.combine(fecha, hora_fin), zona),
    )


def reservar(espacio, personas=8, estado=Reservacion.CONFIRMADA, intervalo=None):
    inicio, fin = intervalo or proximo_lunes()
    return Reservacion.objects.create(
        espacio=espacio, inicio=inicio, fin=fin, cantidad_personas=personas, estado=estado,
    )


def foto_temporal(nombre='nueva.png'):
    archivo = SimpleUploadedFile(nombre, png(), content_type='image/png')
    return {'id': None, **almacen_imagenes.guardar_temporal(archivo, 'PNG')}


def foto_guardada(foto):
    return {'id': foto.pk, 'nombre_archivo': foto.nombre_archivo, 'ruta': foto.archivo.name, 'formato': foto.formato}


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class EditarEspacioServicioTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        usuario = Usuario.objects.create_user(
            correo='clinica@ejemplo.com', password='Reserva2026-Hub', nombre='Clínica Ejemplo',
            es_empresa=True, is_active=True,
        )
        self.empresa = Empresa.objects.create(usuario=usuario, rfc='CEJ010203AB1')
        self.espacio = crear_espacio_publicado(self.empresa)
        self.foto = self.espacio.fotografias.get()
        self.datos = {**DATOS_GENERALES, 'nombre': 'Sala renovada', 'dimensiones_m2': Decimal('45.50')}
        self.tarifa = Tarifa(precio=Decimal('400'), periodo=Tarifa.POR_DIA)
        self.horarios = [HorarioDisponible(dia='lunes', hora_inicio=time(8), hora_fin=time(20))]

    def actualizar(self, fotografias=None, horarios=None):
        return servicio.actualizar_espacio(
            self.empresa, self.espacio.pk, self.datos, self.tarifa,
            horarios or self.horarios, fotografias or [foto_guardada(self.foto)],
        )

    # --- búsqueda ---

    def test_buscar_espacio_de_otra_empresa(self):
        usuario = Usuario.objects.create_user(
            correo='otra@ejemplo.com', password='Reserva2026-Hub', nombre='Otra', es_empresa=True, is_active=True,
        )
        otra = Empresa.objects.create(usuario=usuario, rfc='OTR010203AB1')
        with self.assertRaises(servicio.EspacioNoEncontrado):
            servicio.buscar_espacio(otra, self.espacio.pk)
        with self.assertRaises(servicio.EspacioNoEncontrado):
            servicio.buscar_espacio(self.empresa, 9999)

    def test_buscar_espacio_no_publicado(self):
        Espacio.objects.filter(pk=self.espacio.pk).update(estado='')
        with self.assertRaises(servicio.EspacioNoEditable):
            servicio.buscar_espacio(self.empresa, self.espacio.pk)

    def test_buscar_por_empresa(self):
        self.assertEqual(list(servicio.buscar_por_empresa(self.empresa)), [self.espacio])

    def test_buscar_vigentes_ignora_canceladas_y_pasadas(self):
        vigente = reservar(self.espacio)
        reservar(self.espacio, estado=Reservacion.CANCELADA)
        ayer = timezone.now() - timedelta(days=1)
        reservar(self.espacio, intervalo=(ayer, ayer + timedelta(hours=1)))
        self.assertEqual(servicio.buscar_vigentes(self.espacio), [vigente])

    # --- compatibilidad con reservaciones ---

    def test_validar_compatibilidad_sin_problemas(self):
        reservas = [reservar(self.espacio)]
        self.assertEqual(servicio.validar_compatibilidad({'capacidad': 8, 'horarios': self.horarios}, reservas), {})

    def test_validar_compatibilidad_capacidad(self):
        reservas = [reservar(self.espacio, personas=8), reservar(self.espacio, personas=6)]
        errores = servicio.validar_compatibilidad({'capacidad': 5}, reservas)
        self.assertEqual(errores, {'capacidad': servicio.MENSAJES['capacidad_reservaciones'] % 8})

    def test_validar_compatibilidad_horarios(self):
        reservas = [reservar(self.espacio)]
        martes = [HorarioDisponible(dia='martes', hora_inicio=time(9), hora_fin=time(18))]
        errores = servicio.validar_compatibilidad({'capacidad': 10, 'horarios': martes}, reservas)
        self.assertEqual(list(errores), ['horarios'])
        self.assertIn(str(reservas[0]), errores['horarios'])

    # --- actualización ---

    def test_actualizar_espacio(self):
        self.actualizar()
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, 'Sala renovada')
        self.assertEqual(self.espacio.dimensiones_m2, Decimal('45.50'))
        self.assertEqual(self.espacio.tarifa.precio, Decimal('400'))
        self.assertEqual(self.espacio.tarifa.periodo, Tarifa.POR_DIA)
        [horario] = self.espacio.horarios.all()
        self.assertEqual((horario.hora_inicio, horario.hora_fin), (time(8), time(20)))
        self.assertEqual(list(self.espacio.fotografias.all()), [self.foto])
        self.assertEqual(Tarifa.objects.count(), 1)

    def test_actualizar_cambia_fotografias(self):
        nueva = foto_temporal()
        self.actualizar(fotografias=[nueva])
        [guardada] = self.espacio.fotografias.all()
        self.assertEqual(guardada.nombre_archivo, 'nueva.png')
        self.assertTrue(default_storage.exists(guardada.archivo.name))
        self.assertFalse(default_storage.exists(self.foto.archivo.name))  # la quitada se borra
        self.assertFalse(default_storage.exists(nueva['ruta']))  # la temporal se descarta

    def test_revalidar_detecta_reservacion_nueva(self):
        reservar(self.espacio, personas=8)
        self.datos['capacidad'] = 5
        nueva = foto_temporal()
        with self.assertRaises(servicio.EdicionInvalida) as error:
            self.actualizar(fotografias=[foto_guardada(self.foto), nueva])
        self.assertIn('capacidad', error.exception.errores)
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, DATOS_GENERALES['nombre'])
        self.assertEqual(self.espacio.fotografias.count(), 1)
        self.assertTrue(default_storage.exists(nueva['ruta']))  # se conserva para corregir y reintentar

    def test_revalidar_sin_horarios_libres(self):
        horarios = [HorarioDisponible(dia='lunes', hora_inicio=time(8), hora_fin=time(20), disponible=False)]
        with self.assertRaises(servicio.EdicionInvalida) as error:
            self.actualizar(horarios=horarios)
        self.assertIn('horarios', error.exception.errores)

    def test_falla_de_base_de_datos_revierte_todo(self):
        nueva = foto_temporal()
        antes = set(default_storage.listdir(almacen_imagenes.CARPETA_DEFINITIVA)[1])
        with mock.patch.object(HorarioDisponible.objects, 'bulk_create', side_effect=DatabaseError('caída')):
            with self.assertRaises(DatabaseError):
                self.actualizar(fotografias=[nueva])
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, DATOS_GENERALES['nombre'])
        self.assertEqual(self.espacio.tarifa.precio, Decimal('350'))
        self.assertEqual(self.espacio.horarios.count(), 1)
        self.assertEqual(list(self.espacio.fotografias.all()), [self.foto])
        self.assertTrue(default_storage.exists(self.foto.archivo.name))
        self.assertTrue(default_storage.exists(nueva['ruta']))
        despues = set(default_storage.listdir(almacen_imagenes.CARPETA_DEFINITIVA)[1])
        self.assertEqual(despues, antes)  # la copia definitiva de la foto nueva se eliminó

    def test_falla_al_guardar_imagenes(self):
        with mock.patch.object(
            almacen_imagenes, 'guardar_fotografias', side_effect=almacen_imagenes.ErrorAlmacenamiento,
        ):
            with self.assertRaises(almacen_imagenes.ErrorAlmacenamiento):
                self.actualizar(fotografias=[foto_temporal()])
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, DATOS_GENERALES['nombre'])

    def test_descartar_temporales_no_borra_las_guardadas(self):
        nueva = foto_temporal()
        servicio.descartar_temporales([foto_guardada(self.foto), nueva])
        self.assertTrue(default_storage.exists(self.foto.archivo.name))
        self.assertFalse(default_storage.exists(nueva['ruta']))
