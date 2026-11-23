from unittest import mock

from django.contrib.auth import SESSION_KEY
from django.core import mail
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Empresa, Usuario

CLAVE = 'Reserva2026-Hub'
URL = reverse('cuentas:iniciar_sesion')
INICIO = reverse('cuentas:inicio')


def crear_activo(correo='ana@ejemplo.com', es_empresa=False, **extra):
    usuario = Usuario.objects.create_user(
        correo, CLAVE, nombre='Ana Pérez', es_empresa=es_empresa,
        is_active=True, correo_verificado_en=timezone.now(), **extra,
    )
    if es_empresa:
        Empresa.objects.create(usuario=usuario, rfc='CSO010203AB1')
    return usuario


def credenciales(**cambios):
    datos = {'correo': 'ana@ejemplo.com', 'password': CLAVE}
    datos.update(cambios)
    return datos


class FlujoNormalTests(TestCase):
    def assertSinSesion(self):
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_formulario_se_muestra(self):
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Iniciar sesión')

    def test_cliente_activo_inicia_sesion(self):
        usuario = crear_activo()
        respuesta = self.client.post(URL, credenciales())
        self.assertRedirects(respuesta, INICIO)
        self.assertEqual(self.client.session[SESSION_KEY], str(usuario.pk))
        pantalla = self.client.get(INICIO)
        self.assertContains(pantalla, 'Hola, Ana Pérez')
        self.assertContains(pantalla, 'Cuenta de cliente')
        self.assertNotContains(pantalla, 'Publicar espacio')

    def test_empresa_activa_ve_accesos_de_empresa(self):
        crear_activo(es_empresa=True)
        self.client.post(URL, credenciales())
        pantalla = self.client.get(INICIO)
        self.assertContains(pantalla, 'Cuenta de empresa')
        self.assertContains(pantalla, 'Mis espacios')
        self.assertContains(pantalla, 'Publicar espacio')

    def test_el_correo_no_distingue_mayusculas(self):
        crear_activo()
        respuesta = self.client.post(URL, credenciales(correo='  ANA@Ejemplo.COM '))
        self.assertRedirects(respuesta, INICIO)

    def test_el_inicio_registra_last_login(self):
        usuario = crear_activo()
        self.assertIsNone(usuario.last_login)
        self.client.post(URL, credenciales())
        usuario.refresh_from_db()
        self.assertIsNotNone(usuario.last_login)

    def test_administrador_ve_enlace_al_panel(self):
        Usuario.objects.create_superuser('admin@ejemplo.com', CLAVE, nombre='Admin')
        self.client.post(URL, credenciales(correo='admin@ejemplo.com'))
        pantalla = self.client.get(INICIO)
        self.assertContains(pantalla, 'Administrador')
        self.assertContains(pantalla, '/admin/')

    def test_si_ya_hay_sesion_se_redirige_al_inicio(self):
        self.client.force_login(crear_activo())
        self.assertRedirects(self.client.get(URL), INICIO)

    def test_flujo_completo_registro_verificacion_e_inicio_de_sesion(self):
        self.client.post(reverse('cuentas:registro'), {
            'tipo_cuenta': 'cliente', 'nombre': 'Luis', 'correo': 'luis@ejemplo.com',
            'password1': CLAVE, 'password2': CLAVE, 'rfc': '',
        })
        # Antes de verificar no se puede entrar.
        self.client.post(URL, credenciales(correo='luis@ejemplo.com'))
        self.assertSinSesion()
        token = mail.outbox[0].body.split('/cuentas/verificar/')[1].split('/')[0]
        self.client.get(reverse('cuentas:verificar', args=[token]))
        respuesta = self.client.post(URL, credenciales(correo='luis@ejemplo.com'))
        self.assertRedirects(respuesta, INICIO)


class FlujosAlternativosTests(TestCase):
    def assertSinSesion(self):
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_a1_contrasena_vacia(self):
        crear_activo()
        respuesta = self.client.post(URL, credenciales(password=''))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ambos campos son obligatorios.')
        self.assertSinSesion()

    def test_a1_correo_vacio(self):
        crear_activo()
        respuesta = self.client.post(URL, credenciales(correo=''))
        self.assertContains(respuesta, 'Ambos campos son obligatorios.')
        self.assertSinSesion()

    def test_a1_ambos_vacios(self):
        respuesta = self.client.post(URL, {'correo': '', 'password': ''})
        self.assertContains(respuesta, 'Ambos campos son obligatorios.')
        self.assertSinSesion()

    def test_a2_contrasena_incorrecta_conserva_el_correo(self):
        crear_activo()
        respuesta = self.client.post(URL, credenciales(password='Otra-Clave-2026'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertContains(respuesta, 'value="ana@ejemplo.com"')
        self.assertNotContains(respuesta, 'Otra-Clave-2026')
        self.assertSinSesion()

    def test_a2_correo_inexistente_da_el_mismo_mensaje(self):
        crear_activo()
        con_clave_mala = self.client.post(URL, credenciales(password='Otra-Clave-2026'))
        sin_cuenta = self.client.post(URL, credenciales(correo='nadie@ejemplo.com'))
        self.assertContains(sin_cuenta, 'Correo o contraseña incorrectos.')
        self.assertEqual(
            list(con_clave_mala.context['form'].non_field_errors()),
            list(sin_cuenta.context['form'].non_field_errors()),
        )
        self.assertSinSesion()

    def test_a2_correo_inexistente_tambien_calcula_un_hash(self):
        with mock.patch('cuentas.servicios.autenticacion.make_password') as hash_relleno:
            self.client.post(URL, credenciales(correo='nadie@ejemplo.com'))
        hash_relleno.assert_called_once()

    def test_correo_con_formato_invalido(self):
        respuesta = self.client.post(URL, credenciales(correo='ana.ejemplo.com'))
        self.assertContains(respuesta, 'Ingresa un correo electrónico válido.')
        self.assertSinSesion()

    def test_a3_cuenta_pendiente_no_inicia_sesion(self):
        Usuario.objects.create_user('ana@ejemplo.com', CLAVE, nombre='Ana Pérez')
        respuesta = self.client.post(URL, credenciales())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Confirma tu correo')
        self.assertContains(respuesta, 'Reenviar correo')
        self.assertSinSesion()
        self.assertEqual(len(mail.outbox), 0)

    def test_a3_cuenta_pendiente_con_contrasena_mala_no_revela_el_estado(self):
        Usuario.objects.create_user('ana@ejemplo.com', CLAVE, nombre='Ana Pérez')
        respuesta = self.client.post(URL, credenciales(password='Otra-Clave-2026'))
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertNotContains(respuesta, 'Confirma tu correo')

    def test_cuenta_verificada_pero_desactivada_no_entra(self):
        crear_activo()
        Usuario.objects.filter(correo='ana@ejemplo.com').update(is_active=False)
        respuesta = self.client.post(URL, credenciales())
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertSinSesion()


class FlujoExcepcionalTests(TestCase):
    def test_e1_fallo_de_base_de_datos(self):
        crear_activo()
        with mock.patch.object(Usuario.objects, 'filter', side_effect=DatabaseError('caída')):
            respuesta = self.client.post(URL, credenciales())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Intenta más tarde')
        self.assertNotIn(SESSION_KEY, self.client.session)


class AccesoYRedireccionTests(TestCase):
    def test_el_inicio_exige_sesion(self):
        respuesta = self.client.get(INICIO)
        self.assertRedirects(respuesta, URL + '?next=' + INICIO, fetch_redirect_response=False)

    def test_regresa_a_la_pagina_pedida_si_es_del_mismo_sitio(self):
        crear_activo()
        respuesta = self.client.post(URL, dict(credenciales(), next='/belen/'))
        self.assertRedirects(respuesta, '/belen/', fetch_redirect_response=False)

    def test_ignora_next_hacia_otro_sitio(self):
        crear_activo()
        for destino in ('https://malicioso.example/', '//malicioso.example/'):
            self.client.logout()
            respuesta = self.client.post(URL, dict(credenciales(), next=destino))
            self.assertRedirects(respuesta, INICIO, fetch_redirect_response=False)

    def test_el_formulario_conserva_next(self):
        respuesta = self.client.get(URL + '?next=/belen/')
        self.assertContains(respuesta, 'name="next" value="/belen/"')
