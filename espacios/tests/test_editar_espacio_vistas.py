"""Pruebas de las pantallas de Editar espacio (flujo normal, alternativos y excepcionales).

Google Calendar se simula: ninguna prueba se conecta a Internet.
"""
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.core.files.storage import default_storage
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from cuentas.models import Usuario
from espacios.models import Espacio, HorarioDisponible, Reservacion
from espacios.servicios import almacen_imagenes, google_calendar
from espacios.tests.test_editar_espacio_servicio import crear_espacio_publicado, reservar
from espacios.tests.test_vistas import (
    CLAVE, PASO_1, crear_empresa, imagen, lunes_ocupado, paso_2, sin_conflictos,
)
from espacios.views import SESION_BORRADOR
from espacios.views_edicion import SESION_EDICION

MEDIA_PRUEBAS = tempfile.mkdtemp()


def no_debe_sincronizar(id_calendario, horarios):
    raise AssertionError('No debía consultarse Google Calendar')


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class EditarEspacioVistasTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.empresa = crear_empresa()
        self.client.force_login(self.empresa.usuario)
        self.espacio = crear_espacio_publicado(self.empresa)
        self.foto = self.espacio.fotografias.get()

    # --- utilidades ---

    def url(self, nombre):
        return reverse('espacios:%s' % nombre, args=[self.espacio.pk])

    def abrir(self):
        respuesta = self.client.get(self.url('abrir_edicion'))
        self.assertRedirects(respuesta, self.url('editar_informacion'))

    def paso_1(self, **cambios):
        return self.client.post(self.url('editar_informacion'), {**PASO_1, **cambios})

    def paso_2(self, accion, *filas, revisar=no_debe_sincronizar, **kwargs):
        with mock.patch.object(google_calendar, 'revisar_horarios', side_effect=revisar):
            return self.client.post(self.url('editar_precio_y_horarios'), paso_2(accion, *filas, **kwargs))

    def hasta_revisar(self, **cambios):
        self.abrir()
        self.assertRedirects(self.paso_1(**cambios), self.url('editar_precio_y_horarios'))
        self.assertRedirects(self.paso_2('siguiente'), self.url('revisar_y_guardar'))

    def guardar(self):
        return self.client.post(self.url('revisar_y_guardar'), {'accion': 'guardar'})

    def borrador(self):
        return self.client.session.get(SESION_EDICION, {})

    # --- acceso ---

    def test_sin_sesion_redirige_a_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.get(self.url('abrir_edicion'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('cuentas:iniciar_sesion'), respuesta['Location'])

    def test_cliente_no_puede_editar(self):
        cliente = Usuario.objects.create_user(correo='ana@ejemplo.com', password=CLAVE, nombre='Ana', is_active=True)
        self.client.force_login(cliente)
        self.assertEqual(self.client.get(self.url('abrir_edicion')).status_code, 403)

    def test_no_puede_editar_el_espacio_de_otra_empresa(self):
        otra = crear_empresa('otra@ejemplo.com')
        self.client.force_login(otra.usuario)
        self.assertEqual(self.client.get(self.url('abrir_edicion')).status_code, 404)
        self.assertEqual(self.client.post(self.url('revisar_y_guardar')).status_code, 404)

    def test_espacio_no_publicado_regresa_a_mis_espacios(self):
        Espacio.objects.filter(pk=self.espacio.pk).update(estado='')
        self.assertRedirects(self.client.get(self.url('abrir_edicion')), reverse('espacios:mis_espacios'))

    def test_pasos_sin_abrir_la_edicion_la_abren(self):
        for nombre in ('editar_informacion', 'editar_precio_y_horarios', 'revisar_y_guardar'):
            self.assertRedirects(
                self.client.get(self.url(nombre)), self.url('abrir_edicion'), fetch_redirect_response=False,
            )

    # --- Mis espacios y carga de datos ---

    def test_mis_espacios_ofrece_editar(self):
        self.assertContains(self.client.get(reverse('espacios:mis_espacios')), self.url('abrir_edicion'))

    def test_abrir_carga_los_datos_del_espacio(self):
        self.abrir()
        respuesta = self.client.get(self.url('editar_informacion'))
        self.assertContains(respuesta, '<h1>Editar espacio</h1>', html=True)
        self.assertContains(respuesta, 'value="Sala de juntas Central"')
        self.assertContains(respuesta, 'Dimensiones (m²)')
        self.assertContains(respuesta, self.foto.archivo.url)
        self.assertContains(respuesta, self.url('cancelar_edicion'))
        borrador = self.borrador()
        self.assertTrue(borrador['calendario_sincronizado'])
        self.assertEqual(borrador['tarifa'], {'precio': '350.00', 'periodo': 'hora'})
        self.assertEqual(borrador['fotografias'][0]['id'], self.foto.pk)

    def test_la_edicion_no_toca_el_borrador_de_publicar(self):
        self.client.post(reverse('espacios:formulario_espacio'), {**PASO_1, 'nombre': 'Otro', 'fotografias': [imagen()]})
        self.abrir()
        self.assertEqual(self.client.session[SESION_BORRADOR]['datos_generales']['nombre'], 'Otro')

    # --- flujo normal ---

    def test_editar_informacion_sin_volver_a_sincronizar(self):
        self.hasta_revisar(nombre='Sala renovada', dimensiones_m2='45.5')
        respuesta = self.client.get(self.url('revisar_y_guardar'))
        self.assertContains(respuesta, 'Sala renovada')
        self.assertContains(respuesta, '45.5 m²')
        self.assertContains(respuesta, 'Guardar cambios')
        respuesta = self.guardar()
        self.assertRedirects(respuesta, self.url('espacio_actualizado'))
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, 'Sala renovada')
        self.assertEqual(self.espacio.dimensiones_m2, Decimal('45.5'))
        self.assertEqual(self.espacio.horarios.count(), 1)
        self.assertEqual(self.borrador(), {})
        confirmacion = self.client.get(respuesta['Location'])
        self.assertContains(confirmacion, 'Los cambios del espacio se guardaron correctamente')
        self.assertContains(confirmacion, 'Volver a Mis espacios')

    def test_cambiar_precio_exige_sincronizar(self):
        self.abrir()
        self.paso_1()
        respuesta = self.paso_2('siguiente', precio='400')
        self.assertContains(respuesta, 'Sincronización pendiente')
        self.assertFalse(self.borrador()['calendario_sincronizado'])
        self.assertContains(self.paso_2('sincronizar', precio='400', revisar=sin_conflictos), 'calendario sincronizado')
        self.assertRedirects(self.paso_2('siguiente', precio='400'), self.url('revisar_y_guardar'))
        self.guardar()
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.tarifa.precio, Decimal('400'))

    def test_agregar_horario_invalida_la_sincronizacion(self):
        self.abrir()
        self.paso_1()
        self.paso_2('agregar_horario')
        self.assertFalse(self.borrador()['calendario_sincronizado'])
        self.assertRedirects(self.client.get(self.url('revisar_y_guardar')), self.url('editar_precio_y_horarios'))

    def test_horarios_ocupados_en_google_calendar(self):
        self.abrir()
        self.paso_1()
        filas = (('lunes', '09:00', '18:00'), ('martes', '09:00', '18:00'))
        respuesta = self.paso_2('sincronizar', *filas, revisar=lunes_ocupado)
        self.assertContains(respuesta, 'Ocupado en Google Calendar')
        self.paso_2('siguiente', *filas)
        self.guardar()
        disponibles = HorarioDisponible.objects.filter(espacio=self.espacio, disponible=True)
        self.assertEqual(list(disponibles.values_list('dia', flat=True)), ['martes'])

    # --- reservaciones vigentes ---

    def test_capacidad_menor_a_una_reservacion(self):
        reservar(self.espacio, personas=8)
        self.abrir()
        respuesta = self.paso_1(capacidad='5')
        self.assertContains(respuesta, 'La capacidad no puede ser menor a 8 personas')
        self.assertEqual(self.borrador()['datos_generales']['capacidad'], 10)

    def test_quitar_el_horario_de_una_reservacion(self):
        reservar(self.espacio)
        self.abrir()
        self.paso_1()
        martes = ('martes', '09:00', '18:00')
        self.paso_2('sincronizar', martes, revisar=sin_conflictos)
        respuesta = self.paso_2('siguiente', martes)
        self.assertContains(respuesta, 'Hay reservaciones vigentes fuera de los horarios disponibles')

    def test_reservacion_cancelada_no_impide_cambios(self):
        reservar(self.espacio, personas=8, estado=Reservacion.CANCELADA)
        self.hasta_revisar(capacidad='5')
        self.assertRedirects(self.guardar(), self.url('espacio_actualizado'))

    def test_reservacion_creada_durante_la_edicion(self):
        self.hasta_revisar(capacidad='5')
        reservar(self.espacio, personas=8)
        respuesta = self.guardar()
        self.assertContains(respuesta, 'La capacidad no puede ser menor a 8 personas')
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.capacidad, 10)

    # --- fotografías ---

    def test_quitar_y_agregar_fotografias(self):
        self.abrir()
        self.client.post(self.url('editar_informacion'), {**PASO_1, 'quitar_fotografia': '0'})
        self.assertEqual(self.borrador()['fotografias'], [])
        self.assertTrue(default_storage.exists(self.foto.archivo.name))  # aún no se borra
        self.assertRedirects(self.paso_1(fotografias=[imagen('nueva.png')]), self.url('editar_precio_y_horarios'))
        self.paso_2('siguiente')
        self.guardar()
        [foto] = self.espacio.fotografias.all()
        self.assertEqual(foto.nombre_archivo, 'nueva.png')
        self.assertFalse(default_storage.exists(self.foto.archivo.name))

    def test_quitar_todas_las_fotografias(self):
        self.abrir()
        self.client.post(self.url('editar_informacion'), {**PASO_1, 'quitar_fotografia': '0'})
        self.assertContains(self.paso_1(), 'Agregue al menos una fotografía')

    # --- cancelar ---

    def test_cancelar_descarta_los_cambios(self):
        self.abrir()
        self.paso_1(nombre='No se guarda', fotografias=[imagen('nueva.png')])
        temporal = self.borrador()['fotografias'][1]['ruta']
        respuesta = self.client.post(self.url('cancelar_edicion'))
        self.assertRedirects(respuesta, reverse('espacios:mis_espacios'))
        self.assertEqual(self.borrador(), {})
        self.assertFalse(default_storage.exists(temporal))
        self.assertTrue(default_storage.exists(self.foto.archivo.name))
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, 'Sala de juntas Central')

    # --- flujos excepcionales ---

    def test_falla_al_guardar_e2(self):
        self.hasta_revisar(nombre='Sala renovada')
        with mock.patch.object(HorarioDisponible.objects, 'bulk_create', side_effect=DatabaseError('caída')):
            respuesta = self.guardar()
        self.assertContains(respuesta, 'No fue posible guardar los cambios. Intente nuevamente más tarde')
        self.espacio.refresh_from_db()
        self.assertEqual(self.espacio.nombre, 'Sala de juntas Central')
        self.assertEqual(self.espacio.horarios.count(), 1)
        self.assertIn('datos_generales', self.borrador())  # se conserva para reintentar

    def test_falla_al_guardar_imagenes_e3(self):
        self.abrir()
        self.paso_1(fotografias=[imagen('nueva.png')])
        self.paso_2('siguiente')
        with mock.patch.object(
            almacen_imagenes, 'guardar_fotografias', side_effect=almacen_imagenes.ErrorAlmacenamiento,
        ):
            respuesta = self.guardar()
        self.assertContains(respuesta, 'Ocurrió un problema al guardar las imágenes')
        self.assertEqual(self.espacio.fotografias.count(), 1)

    def test_google_calendar_no_disponible_e1(self):
        self.abrir()
        self.paso_1()
        respuesta = self.paso_2('sincronizar', precio='400', revisar=google_calendar.CalendarioNoDisponible())
        self.assertContains(respuesta, 'No fue posible sincronizar el calendario. Intente nuevamente más tarde')
        self.assertFalse(self.borrador()['calendario_sincronizado'])
