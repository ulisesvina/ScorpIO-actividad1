"""Pruebas de las pantallas de Publicar espacio (flujo normal, alternativos y excepcionales).

Google Calendar se simula: ninguna prueba se conecta a Internet.
"""
import io
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from cuentas.models import Empresa, Usuario
from espacios.models import Espacio, HorarioDisponible
from espacios.servicios import almacen_imagenes, google_calendar
from espacios.views import SESION_BORRADOR

MEDIA_PRUEBAS = tempfile.mkdtemp()
CLAVE = 'Reserva2026-Hub'


def imagen(nombre='sala.png'):
    contenido = io.BytesIO()
    Image.new('RGB', (2, 2)).save(contenido, 'PNG')
    return SimpleUploadedFile(nombre, contenido.getvalue(), content_type='image/png')


def crear_empresa(correo='clinica@ejemplo.com', id_calendario='clinica@ejemplo.com'):
    usuario = Usuario.objects.create_user(
        correo=correo, password=CLAVE, nombre='Clínica Ejemplo', es_empresa=True, is_active=True,
    )
    return Empresa.objects.create(usuario=usuario, rfc='CEJ010203AB1', id_calendario=id_calendario)


PASO_1 = {
    'nombre': 'Sala de juntas Central',
    'descripcion': 'Espacio equipado para reuniones',
    'capacidad': '10',
    'direccion': 'Av. Reforma 123',
}


def paso_2(accion, *filas, precio='350', periodo='hora'):
    filas = filas or (('lunes', '09:00', '18:00'),)
    datos = {
        'precio': precio, 'periodo': periodo, 'accion': accion,
        'form-TOTAL_FORMS': str(len(filas)), 'form-INITIAL_FORMS': str(len(filas)),
    }
    for i, (dia, inicio, fin) in enumerate(filas):
        datos.update({
            'form-%d-dia' % i: dia, 'form-%d-hora_inicio' % i: inicio,
            'form-%d-hora_fin' % i: fin, 'form-%d-disponible' % i: 'on',
        })
    return datos


def sin_conflictos(id_calendario, horarios):
    return []


def todo_ocupado(id_calendario, horarios):
    for horario in horarios:
        horario.disponible = False
    return list(horarios)


def lunes_ocupado(id_calendario, horarios):
    horarios[0].disponible = False
    return [horarios[0]]


@override_settings(MEDIA_ROOT=MEDIA_PRUEBAS)
class PublicarEspacioVistasTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_PRUEBAS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.empresa = crear_empresa()
        self.client.force_login(self.empresa.usuario)

    # --- utilidades ---

    def llenar_paso_1(self):
        respuesta = self.client.post(reverse('espacios:formulario_espacio'), {**PASO_1, 'fotografias': [imagen()]})
        self.assertRedirects(respuesta, reverse('espacios:precio_y_horarios'))

    def sincronizar(self, *filas, revisar=sin_conflictos, **kwargs):
        with mock.patch.object(google_calendar, 'revisar_horarios', side_effect=revisar):
            return self.client.post(reverse('espacios:precio_y_horarios'), paso_2('sincronizar', *filas, **kwargs))

    def hasta_revisar(self):
        self.llenar_paso_1()
        self.sincronizar()
        respuesta = self.client.post(reverse('espacios:precio_y_horarios'), paso_2('siguiente'))
        self.assertRedirects(respuesta, reverse('espacios:revisar_y_publicar'))

    def borrador(self):
        return self.client.session.get(SESION_BORRADOR, {})

    # --- acceso ---

    def test_sin_sesion_redirige_a_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse('espacios:mis_espacios'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('cuentas:iniciar_sesion'), respuesta['Location'])

    def test_cliente_no_puede_publicar(self):
        cliente = Usuario.objects.create_user(correo='ana@ejemplo.com', password=CLAVE, nombre='Ana', is_active=True)
        self.client.force_login(cliente)
        self.assertEqual(self.client.get(reverse('espacios:formulario_espacio')).status_code, 403)

    # --- Mis espacios ---

    def test_mis_espacios_vacio(self):
        respuesta = self.client.get(reverse('espacios:mis_espacios'))
        self.assertContains(respuesta, 'Todavía no tienes espacios publicados.')
        self.assertContains(respuesta, '+ Publicar espacio')

    def test_mis_espacios_solo_muestra_los_de_la_empresa(self):
        otra = crear_empresa('otra@ejemplo.com')
        Espacio.objects.create(empresa=otra, nombre='Ajeno', descripcion='x', capacidad=1, direccion='x', estado='publicado')
        Espacio.objects.create(
            empresa=self.empresa, nombre='Propio', descripcion='x', capacidad=1, direccion='x', estado='publicado',
        )
        respuesta = self.client.get(reverse('espacios:mis_espacios'))
        self.assertContains(respuesta, 'Propio')
        self.assertNotContains(respuesta, 'Ajeno')

    # --- Paso 1 ---

    def test_paso_1_valido_guarda_borrador_y_fotos_temporales(self):
        self.llenar_paso_1()
        borrador = self.borrador()
        self.assertEqual(borrador['datos_generales']['nombre'], 'Sala de juntas Central')
        [foto] = borrador['fotografias']
        self.assertTrue(default_storage.exists(foto['ruta']))
        self.assertFalse(Espacio.objects.exists())  # nada se guarda antes de publicar

    def test_paso_1_muestra_la_empresa(self):
        self.assertContains(self.client.get(reverse('espacios:formulario_espacio')), 'Clínica Ejemplo')

    def test_paso_1_campos_vacios_conserva_lo_capturado_a1(self):
        respuesta = self.client.post(
            reverse('espacios:formulario_espacio'), {**PASO_1, 'nombre': '', 'fotografias': [imagen()]},
        )
        self.assertContains(respuesta, 'Ingrese el nombre del espacio')
        self.assertContains(respuesta, 'Av. Reforma 123')
        self.assertEqual(len(self.borrador()['fotografias']), 1)  # la foto válida se conserva

    def test_paso_1_falla_al_guardar_imagenes_e3(self):
        with mock.patch.object(almacen_imagenes, 'guardar_temporal', side_effect=almacen_imagenes.ErrorAlmacenamiento):
            respuesta = self.client.post(reverse('espacios:formulario_espacio'), {**PASO_1, 'fotografias': [imagen()]})
        self.assertContains(respuesta, 'Ocurrió un problema al guardar las imágenes. Intente nuevamente')

    def test_quitar_fotografia(self):
        self.llenar_paso_1()
        ruta = self.borrador()['fotografias'][0]['ruta']
        self.client.post(reverse('espacios:formulario_espacio'), {**PASO_1, 'quitar_fotografia': '0'})
        self.assertEqual(self.borrador()['fotografias'], [])
        self.assertFalse(default_storage.exists(ruta))

    # --- Paso 2 ---

    def test_paso_2_sin_paso_1_regresa(self):
        self.assertRedirects(
            self.client.get(reverse('espacios:precio_y_horarios')), reverse('espacios:formulario_espacio'),
        )

    def test_sincronizar_sin_conflictos(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar()
        self.assertContains(respuesta, 'Datos guardados y calendario sincronizado')
        self.assertTrue(self.borrador()['calendario_sincronizado'])

    def test_precio_y_modalidad_invalidos_a3(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar(precio='0', periodo='')
        self.assertContains(respuesta, 'El precio debe ser mayor que cero')
        self.assertContains(respuesta, 'Seleccione un periodo de reservación')

    def test_horarios_invalidos_a4(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar(('lunes', '18:00', '09:00'))
        self.assertContains(respuesta, 'Verifique los horarios ingresados')
        self.assertContains(respuesta, 'fila-error')

    def test_conflicto_parcial_a9(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar(('lunes', '09:00', '18:00'), ('martes', '09:00', '18:00'), revisar=lunes_ocupado)
        self.assertContains(respuesta, 'Ocupado en Google Calendar')
        self.assertContains(respuesta, 'Solo se publicarán los horarios disponibles')
        lunes, martes = self.borrador()['horarios']
        self.assertTrue(lunes['ocupado'])
        self.assertFalse(martes['ocupado'])

    def test_todos_ocupados_a10(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar(revisar=todo_ocupado)
        self.assertContains(respuesta, 'No quedan horarios disponibles')
        siguiente = self.client.post(reverse('espacios:precio_y_horarios'), paso_2('siguiente'))
        self.assertEqual(siguiente.status_code, 200)  # no avanza

    def test_google_calendar_no_disponible_e1(self):
        self.llenar_paso_1()
        respuesta = self.sincronizar(revisar=google_calendar.CalendarioNoDisponible())
        self.assertContains(respuesta, 'No fue posible sincronizar el calendario. Intente nuevamente más tarde')
        self.assertFalse(self.borrador()['calendario_sincronizado'])
        self.assertEqual(self.borrador()['tarifa']['precio'], '350')  # se conserva lo capturado

    def test_sin_calendario_vinculado_ofrece_vincularlo(self):
        self.empresa.id_calendario = ''
        self.empresa.save()
        self.llenar_paso_1()
        self.assertContains(self.client.get(reverse('espacios:precio_y_horarios')), 'Vincular Google Calendar')

    def test_siguiente_sin_sincronizar_no_avanza(self):
        self.llenar_paso_1()
        respuesta = self.client.post(reverse('espacios:precio_y_horarios'), paso_2('siguiente'))
        self.assertContains(respuesta, 'Sincronización pendiente')

    def test_cambiar_datos_despues_de_sincronizar_pide_sincronizar_de_nuevo(self):
        self.llenar_paso_1()
        self.sincronizar()
        respuesta = self.client.post(reverse('espacios:precio_y_horarios'), paso_2('siguiente', precio='400'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.borrador()['calendario_sincronizado'])

    def test_agregar_horario(self):
        self.llenar_paso_1()
        respuesta = self.client.post(reverse('espacios:precio_y_horarios'), paso_2('agregar_horario'))
        self.assertEqual(respuesta.context['horarios_form'].total_form_count(), 2)

    # --- Paso 3 y publicación ---

    def test_revisar_muestra_el_resumen(self):
        self.hasta_revisar()
        respuesta = self.client.get(reverse('espacios:revisar_y_publicar'))
        self.assertContains(respuesta, 'Sala de juntas Central')
        self.assertContains(respuesta, 'Lunes 09:00–18:00')
        self.assertContains(respuesta, '$350 / hora')
        self.assertContains(respuesta, 'Sincronizado')

    def test_publicar_flujo_normal_n1(self):
        self.hasta_revisar()
        respuesta = self.client.post(reverse('espacios:revisar_y_publicar'), {'accion': 'publicar'})
        espacio = Espacio.objects.get()
        self.assertRedirects(respuesta, reverse('espacios:espacio_publicado', args=[espacio.pk]))
        self.assertEqual(espacio.empresa, self.empresa)
        self.assertEqual(espacio.estado, Espacio.PUBLICADO)
        self.assertEqual(espacio.tarifa.precio, Decimal('350'))
        self.assertEqual(espacio.fotografias.count(), 1)
        self.assertEqual(self.borrador(), {})
        confirmacion = self.client.get(respuesta['Location'])
        self.assertContains(confirmacion, 'El espacio se publicó correctamente')
        self.assertContains(confirmacion, 'Volver a Mis espacios')

    def test_horarios_ocupados_se_guardan_como_no_disponibles(self):
        self.llenar_paso_1()
        self.sincronizar(('lunes', '09:00', '18:00'), ('martes', '09:00', '18:00'), revisar=lunes_ocupado)
        self.client.post(
            reverse('espacios:precio_y_horarios'),
            paso_2('siguiente', ('lunes', '09:00', '18:00'), ('martes', '09:00', '18:00')),
        )
        self.client.post(reverse('espacios:revisar_y_publicar'), {'accion': 'publicar'})
        disponibles = HorarioDisponible.objects.filter(disponible=True).values_list('dia', flat=True)
        self.assertEqual(list(disponibles), ['martes'])

    def test_falla_al_publicar_e2(self):
        self.hasta_revisar()
        with mock.patch.object(HorarioDisponible.objects, 'bulk_create', side_effect=DatabaseError('caída')):
            respuesta = self.client.post(reverse('espacios:revisar_y_publicar'), {'accion': 'publicar'})
        self.assertContains(respuesta, 'No fue posible publicar el espacio. Intente nuevamente más tarde')
        self.assertFalse(Espacio.objects.exists())
        self.assertIn('datos_generales', self.borrador())  # se conserva para reintentar

    def test_falla_al_guardar_imagenes_al_publicar_e3(self):
        self.hasta_revisar()
        with mock.patch.object(
            almacen_imagenes, 'guardar_fotografias', side_effect=almacen_imagenes.ErrorAlmacenamiento,
        ):
            respuesta = self.client.post(reverse('espacios:revisar_y_publicar'), {'accion': 'publicar'})
        self.assertContains(respuesta, 'Ocurrió un problema al guardar las imágenes')
        self.assertFalse(Espacio.objects.exists())

    def test_no_se_puede_ver_la_confirmacion_de_otra_empresa(self):
        otra = crear_empresa('otra@ejemplo.com')
        ajeno = Espacio.objects.create(
            empresa=otra, nombre='Ajeno', descripcion='x', capacidad=1, direccion='x', estado='publicado',
        )
        self.assertEqual(self.client.get(reverse('espacios:espacio_publicado', args=[ajeno.pk])).status_code, 404)

    def test_cancelar_descarta_todo(self):
        self.llenar_paso_1()
        ruta = self.borrador()['fotografias'][0]['ruta']
        respuesta = self.client.post(reverse('espacios:cancelar'))
        self.assertRedirects(respuesta, reverse('espacios:mis_espacios'))
        self.assertEqual(self.borrador(), {})
        self.assertFalse(default_storage.exists(ruta))

    # --- Vincular Google Calendar ---

    def test_vincular_calendario(self):
        self.empresa.id_calendario = ''
        self.empresa.save()
        with mock.patch.object(google_calendar, 'consultar_eventos', return_value=[]):
            respuesta = self.client.post(reverse('espacios:vincular_calendario'), {'id_calendario': ' mi@gmail.com '})
        self.assertRedirects(respuesta, reverse('espacios:mis_espacios'))
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.id_calendario, 'mi@gmail.com')

    def test_vincular_calendario_no_compartido(self):
        with mock.patch.object(google_calendar, 'consultar_eventos', side_effect=google_calendar.CalendarioSinAcceso):
            respuesta = self.client.post(reverse('espacios:vincular_calendario'), {'id_calendario': 'mi@gmail.com'})
        self.assertContains(respuesta, 'No fue posible acceder a su Google Calendar')
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.id_calendario, 'clinica@ejemplo.com')
