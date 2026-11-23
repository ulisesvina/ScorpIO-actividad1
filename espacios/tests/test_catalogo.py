from datetime import time
from decimal import Decimal
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from cuentas.models import Usuario
from espacios.models import Espacio, Fotografia, HorarioDisponible, Tarifa
from espacios.servicios import consulta_espacios as consulta
from espacios.tests.test_vistas import CLAVE, crear_empresa

BUSCAR = reverse('espacios:buscar_espacios')
AVISO_NO_DISPONIBLE = 'El espacio consultado ya no se encuentra disponible'
AVISO_SIN_RESULTADOS = 'No se encontraron espacios disponibles con los criterios ingresados'
AVISO_ERROR = 'No fue posible cargar la información del espacio. Por favor, reintenta más tarde'


def crear_espacio(empresa, nombre='Sala Central', direccion='Av. Reforma 123', horarios=(('lunes', 9, 18),),
                  estado=Espacio.PUBLICADO, precio='350'):
    espacio = Espacio.objects.create(
        empresa=empresa, nombre=nombre, descripcion='Espacio equipado para reuniones',
        capacidad=10, direccion=direccion, estado=estado,
    )
    Tarifa.objects.create(espacio=espacio, precio=Decimal(precio), periodo=Tarifa.POR_HORA)
    for dia, inicio, fin in horarios:
        HorarioDisponible.objects.create(espacio=espacio, dia=dia, hora_inicio=time(inicio), hora_fin=time(fin))
    return espacio


class BuscarEspaciosTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa()
        self.client.force_login(self.empresa.usuario)

    def test_requiere_sesion(self):
        self.client.logout()
        respuesta = self.client.get(BUSCAR)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('cuentas:iniciar_sesion'), respuesta['Location'])

    def test_un_cliente_tambien_puede_ver(self):
        crear_espacio(self.empresa)
        cliente = Usuario.objects.create_user('ana@ejemplo.com', CLAVE, nombre='Ana', is_active=True)
        self.client.force_login(cliente)
        self.assertContains(self.client.get(BUSCAR), 'Sala Central')

    def test_lista_con_nombre_ubicacion_y_precio(self):
        crear_espacio(self.empresa)
        respuesta = self.client.get(BUSCAR)
        self.assertContains(respuesta, 'Sala Central')
        self.assertContains(respuesta, 'Av. Reforma 123')
        self.assertContains(respuesta, '$350 / hora')

    def test_no_muestra_espacios_sin_publicar(self):
        crear_espacio(self.empresa, nombre='Borrador', estado='borrador')
        self.assertNotContains(self.client.get(BUSCAR), 'Borrador')

    def test_catalogo_vacio(self):
        self.assertContains(self.client.get(BUSCAR), 'Todavía no hay espacios publicados.')

    def test_filtro_por_texto_a1(self):
        crear_espacio(self.empresa, nombre='Sala Central')
        crear_espacio(self.empresa, nombre='Consultorio Sur')
        respuesta = self.client.get(BUSCAR, {'q': 'consultorio'})
        self.assertContains(respuesta, 'Consultorio Sur')
        self.assertNotContains(respuesta, 'Sala Central')

    def test_filtro_por_ubicacion_a1(self):
        crear_espacio(self.empresa, nombre='Uno', direccion='Av. Reforma 123')
        crear_espacio(self.empresa, nombre='Dos', direccion='Calle Juárez 5')
        respuesta = self.client.get(BUSCAR, {'ubicacion': 'Juárez'})
        self.assertContains(respuesta, 'Dos')
        self.assertNotContains(respuesta, 'Av. Reforma')

    def test_filtro_por_fecha_a1(self):
        crear_espacio(self.empresa, nombre='Solo lunes', horarios=(('lunes', 9, 18),))
        crear_espacio(self.empresa, nombre='Solo martes', horarios=(('martes', 9, 18),))
        respuesta = self.client.get(BUSCAR, {'fecha': '2026-11-23'})  # lunes
        self.assertContains(respuesta, 'Solo lunes')
        self.assertNotContains(respuesta, 'Solo martes')

    def test_filtro_por_fecha_ignora_horarios_ocupados(self):
        espacio = crear_espacio(self.empresa)
        espacio.horarios.update(disponible=False)
        respuesta = self.client.get(BUSCAR, {'fecha': '2026-11-23'})
        self.assertContains(respuesta, AVISO_SIN_RESULTADOS)

    def test_sin_coincidencias_a2(self):
        crear_espacio(self.empresa)
        respuesta = self.client.get(BUSCAR, {'q': 'Sala de conferencias inexistente'})
        self.assertContains(respuesta, AVISO_SIN_RESULTADOS)
        self.assertContains(respuesta, 'Restablecer filtros')

    def test_fecha_invalida(self):
        respuesta = self.client.get(BUSCAR, {'fecha': 'no-es-fecha'})
        self.assertIn('fecha', respuesta.context['form'].errors)

    def test_falla_de_base_de_datos_e1(self):
        with mock.patch.object(consulta, 'buscar', side_effect=DatabaseError('caída')):
            respuesta = self.client.get(BUSCAR)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, AVISO_ERROR)

    def test_aviso_de_espacio_no_disponible(self):
        self.assertContains(self.client.get(BUSCAR, {'aviso': 'no_disponible'}), AVISO_NO_DISPONIBLE)

    def test_aviso_desconocido_se_ignora(self):
        respuesta = self.client.get(BUSCAR, {'aviso': '<script>alert(1)</script>'})
        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertNotContains(respuesta, AVISO_NO_DISPONIBLE)


class DetalleEspacioTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa()
        self.client.force_login(self.empresa.usuario)

    def url(self, espacio):
        return reverse('espacios:detalle_espacio', args=[espacio.pk])

    def test_requiere_sesion(self):
        espacio = crear_espacio(self.empresa)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(espacio)).status_code, 302)

    def test_detalle_normal_n1(self):
        espacio = crear_espacio(self.empresa)
        respuesta = self.client.get(self.url(espacio))
        self.assertContains(respuesta, 'Sala Central')
        self.assertContains(respuesta, 'Espacio equipado para reuniones')
        self.assertContains(respuesta, 'Clínica Ejemplo')
        self.assertContains(respuesta, 'Lunes')
        self.assertContains(respuesta, '09:00–18:00')
        self.assertContains(respuesta, 'Reservar espacio')
        self.assertContains(respuesta, 'Políticas de reservación y cancelación')

    def test_solo_muestra_horarios_disponibles(self):
        espacio = crear_espacio(self.empresa, horarios=(('lunes', 9, 18), ('martes', 9, 18)))
        espacio.horarios.filter(dia='martes').update(disponible=False)
        respuesta = self.client.get(self.url(espacio))
        self.assertContains(respuesta, 'Lunes')
        self.assertNotContains(respuesta, 'Martes')

    def test_espacio_inexistente_a3(self):
        respuesta = self.client.get(reverse('espacios:detalle_espacio', args=[9999]), follow=True)
        self.assertRedirects(respuesta, BUSCAR + '?aviso=no_disponible')
        self.assertContains(respuesta, AVISO_NO_DISPONIBLE)

    def test_espacio_dado_de_baja_a3(self):
        espacio = crear_espacio(self.empresa, estado='borrador')
        respuesta = self.client.get(self.url(espacio), follow=True)
        self.assertContains(respuesta, AVISO_NO_DISPONIBLE)

    def test_falla_de_base_de_datos_e1(self):
        espacio = crear_espacio(self.empresa)
        with mock.patch.object(consulta, 'obtener_publicado', side_effect=DatabaseError('caída')):
            respuesta = self.client.get(self.url(espacio))
        self.assertContains(respuesta, AVISO_ERROR)

    def test_sin_fotografias_usa_imagen_por_defecto_e2(self):
        espacio = crear_espacio(self.empresa)
        self.assertContains(self.client.get(self.url(espacio)), 'sin_imagen.svg')

    def test_imagen_rota_tiene_respaldo_e2(self):
        espacio = crear_espacio(self.empresa)
        Fotografia.objects.create(
            espacio=espacio, nombre_archivo='x.png', archivo='espacios/fotografias/x.png', formato='PNG',
        )
        respuesta = self.client.get(self.url(espacio))
        self.assertContains(respuesta, 'onerror')
        self.assertContains(respuesta, 'Sala Central')  # el texto sigue visible