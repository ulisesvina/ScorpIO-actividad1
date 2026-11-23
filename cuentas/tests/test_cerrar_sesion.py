import time
from unittest import mock

from django.contrib.auth import SESSION_KEY
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from cuentas.middleware import CLAVE_ACTIVIDAD
from cuentas.tests.test_inicio_sesion import crear_activo

URL = reverse('cuentas:cerrar_sesion')
LOGIN = reverse('cuentas:iniciar_sesion')
INICIO = reverse('cuentas:inicio')


class CerrarSesionTests(TestCase):
    def setUp(self):
        self.client.force_login(crear_activo())

    def test_pantalla_de_inicio_muestra_la_confirmacion(self):
        pantalla = self.client.get(INICIO)
        self.assertContains(pantalla, '¿Estás seguro de que deseas salir del sistema?')
        self.assertContains(pantalla, 'Confirmar salida')
        self.assertContains(pantalla, 'data-abrir-cerrar-sesion')

    def test_flujo_normal_n1(self):
        respuesta = self.client.post(URL)
        self.assertRedirects(respuesta, LOGIN)
        self.assertNotIn(SESSION_KEY, self.client.session)
        denegado = self.client.get(INICIO)
        self.assertRedirects(denegado, LOGIN + '?next=' + INICIO, fetch_redirect_response=False)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(URL).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_sin_sesion_solo_redirige(self):
        self.client.logout()
        self.assertRedirects(self.client.post(URL), LOGIN)

    def test_otra_ventana_a2(self):
        self.client.post(URL)  # «pestaña 1» cierra sesión
        respuesta = self.client.get(INICIO, follow=True)  # «pestaña 2» abre una sección privada
        self.assertContains(respuesta, 'La sesión ha sido finalizada en otra ventana')

    def test_sin_cierre_previo_no_hay_aviso_de_otra_ventana(self):
        self.client.logout()
        respuesta = self.client.get(LOGIN + '?next=' + INICIO)
        self.assertNotContains(respuesta, 'finalizada en otra ventana')

    def test_el_cierre_normal_no_muestra_aviso(self):
        respuesta = self.client.post(URL, follow=True)
        self.assertNotContains(respuesta, 'finalizada en otra ventana')

    def test_paginas_privadas_no_se_guardan_en_cache_a3(self):
        respuesta = self.client.get('/belen/')  # página de presentacion, sin decoradores propios
        self.assertIn('no-store', respuesta['Cache-Control'])

    @override_settings(SESION_INACTIVIDAD_SEGUNDOS=60)
    def test_expiracion_por_inactividad_a1(self):
        sesion = self.client.session
        sesion[CLAVE_ACTIVIDAD] = time.time() - 3600
        sesion.save()
        respuesta = self.client.get(INICIO, follow=True)
        self.assertContains(respuesta, 'Tu sesión ha expirado. Por favor, inicia sesión nuevamente')
        self.assertNotIn(SESSION_KEY, self.client.session)

    @override_settings(SESION_INACTIVIDAD_SEGUNDOS=60)
    def test_cerrar_sesion_con_sesion_expirada(self):
        sesion = self.client.session
        sesion[CLAVE_ACTIVIDAD] = time.time() - 3600
        sesion.save()
        respuesta = self.client.post(URL, follow=True)
        self.assertContains(respuesta, 'Tu sesión ha expirado')

    def test_la_actividad_se_registra(self):
        self.client.get(INICIO)
        self.assertIn(CLAVE_ACTIVIDAD, self.client.session)

    def test_error_interno_cierra_la_sesion_local_e2(self):
        with mock.patch('cuentas.views_cierre.logout', side_effect=DatabaseError('caída')):
            respuesta = self.client.post(URL, follow=True)
        self.assertContains(respuesta, 'Ocurrió un error en el servidor, pero tu sesión local ha sido cerrada')
        self.assertNotIn(SESSION_KEY, self.client.session)