from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from cuentas.models import Empresa, EnlaceVerificacion, Usuario

CLAVE = 'Reserva2026-Hub'


def datos_cliente(**cambios):
    datos = {
        'tipo_cuenta': 'cliente',
        'nombre': 'Ana Pérez',
        'correo': 'ana@ejemplo.com',
        'password1': CLAVE,
        'password2': CLAVE,
        'rfc': '',
    }
    datos.update(cambios)
    return datos


def datos_empresa(**cambios):
    return datos_cliente(**{
        'tipo_cuenta': 'empresa',
        'nombre': 'Clínica Sonrisa',
        'correo': 'clinica.sonrisa@ejemplo.com',
        'rfc': 'CSO010203AB1',
        **cambios,
    })


class FlujoNormalTests(TestCase):
    url = reverse('cuentas:registro')

    def test_formulario_se_muestra(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Crear cuenta')

    def test_registro_de_cliente(self):
        respuesta = self.client.post(self.url, datos_cliente())
        self.assertRedirects(respuesta, reverse('cuentas:confirma_correo'))
        usuario = Usuario.objects.get(correo='ana@ejemplo.com')
        self.assertFalse(usuario.is_active)
        self.assertIsNone(usuario.correo_verificado_en)
        self.assertEqual(usuario.estado, 'Pendiente de verificación')
        self.assertFalse(usuario.es_empresa)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(Empresa.objects.exists())
        self.assertNotEqual(usuario.password, CLAVE)
        self.assertTrue(usuario.check_password(CLAVE))

    def test_registro_de_empresa(self):
        respuesta = self.client.post(self.url, datos_empresa(rfc=' cso 010203 ab1 '))
        self.assertRedirects(respuesta, reverse('cuentas:confirma_correo'))
        usuario = Usuario.objects.get(correo='clinica.sonrisa@ejemplo.com')
        self.assertTrue(usuario.es_empresa)
        self.assertFalse(usuario.is_active)
        self.assertEqual(usuario.empresa.rfc, 'CSO010203AB1')

    def test_correo_de_verificacion_enviado(self):
        self.client.post(self.url, datos_cliente())
        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, ['ana@ejemplo.com'])
        self.assertIn('/cuentas/verificar/', mensaje.body)

    def test_pantalla_confirma_tu_correo(self):
        respuesta = self.client.post(self.url, datos_cliente(), follow=True)
        self.assertContains(respuesta, 'Confirma tu correo')
        self.assertContains(respuesta, 'Reenviar correo')

    def test_correo_se_guarda_en_minusculas(self):
        self.client.post(self.url, datos_cliente(correo='ANA@Ejemplo.COM'))
        self.assertTrue(Usuario.objects.filter(correo='ana@ejemplo.com').exists())


class ValidacionesTests(TestCase):
    url = reverse('cuentas:registro')

    def assertSinCuentas(self):
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Empresa.objects.count(), 0)
        self.assertEqual(EnlaceVerificacion.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_campos_obligatorios_incompletos(self):
        respuesta = self.client.post(self.url, {'tipo_cuenta': 'cliente'})
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context['form'].errors
        for campo in ('nombre', 'correo', 'password1', 'password2'):
            self.assertIn(campo, errores)
        self.assertSinCuentas()

    def test_nombre_vacio(self):
        respuesta = self.client.post(self.url, datos_cliente(nombre=''))
        self.assertIn('nombre', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_correo_con_formato_invalido(self):
        respuesta = self.client.post(self.url, datos_cliente(correo='ana.ejemplo.com'))
        self.assertIn('correo', respuesta.context['form'].errors)
        self.assertContains(respuesta, 'Ingresa un correo electrónico válido.')
        self.assertSinCuentas()

    def test_correo_de_cuenta_activa_no_se_duplica(self):
        Usuario.objects.create_user('ana@ejemplo.com', CLAVE, nombre='Otra Ana', is_active=True)
        respuesta = self.client.post(self.url, datos_cliente(correo='ANA@ejemplo.com'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('correo', respuesta.context['form'].errors)
        self.assertContains(respuesta, 'Inicia sesión')
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_de_cuenta_pendiente_reenvia_sin_crear_otra(self):
        self.client.post(self.url, datos_cliente(nombre='Primera'))
        self.assertEqual(len(mail.outbox), 1)
        nueva = 'Otra-Clave-2026!'
        self.client.post(self.url, datos_cliente(nombre='Segunda', password1=nueva, password2=nueva))
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(EnlaceVerificacion.objects.count(), 1)
        usuario = Usuario.objects.get()
        # Los datos del último envío reemplazan a los anteriores (evita secuestro previo del correo).
        self.assertEqual(usuario.nombre, 'Segunda')
        self.assertTrue(usuario.check_password(nueva))
        self.assertFalse(usuario.check_password(CLAVE))

    def test_contrasena_demasiado_corta(self):
        respuesta = self.client.post(self.url, datos_cliente(password1='Ab1', password2='Ab1'))
        self.assertIn('password1', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_contrasena_solo_numerica(self):
        respuesta = self.client.post(self.url, datos_cliente(password1='83920174', password2='83920174'))
        self.assertIn('password1', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_contrasena_parecida_al_correo(self):
        respuesta = self.client.post(self.url, datos_cliente(password1='ana@ejemplo.com', password2='ana@ejemplo.com'))
        self.assertIn('password1', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_contrasenas_distintas(self):
        respuesta = self.client.post(self.url, datos_cliente(password2='Reserva2062-Hub'))
        self.assertIn('password2', respuesta.context['form'].errors)
        self.assertContains(respuesta, 'Las contraseñas no coinciden.')
        self.assertSinCuentas()

    def test_empresa_sin_rfc(self):
        respuesta = self.client.post(self.url, datos_empresa(rfc=''))
        self.assertIn('rfc', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_empresa_con_rfc_invalido(self):
        respuesta = self.client.post(self.url, datos_empresa(rfc='12345'))
        self.assertIn('rfc', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_cliente_ignora_el_rfc_enviado(self):
        self.client.post(self.url, datos_cliente(rfc='CSO010203AB1'))
        self.assertTrue(Usuario.objects.filter(correo='ana@ejemplo.com').exists())
        self.assertFalse(Empresa.objects.exists())

    def test_no_se_puede_registrar_un_administrador(self):
        respuesta = self.client.post(self.url, datos_cliente(tipo_cuenta='admin'))
        self.assertIn('tipo_cuenta', respuesta.context['form'].errors)
        self.assertSinCuentas()

    def test_el_formulario_no_acepta_campos_de_privilegio(self):
        self.client.post(self.url, datos_cliente(is_staff='on', is_superuser='on', is_active='on'))
        usuario = Usuario.objects.get()
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_active)


class FlujosExcepcionalesTests(TestCase):
    url = reverse('cuentas:registro')

    def test_fallo_de_envio_deja_la_cuenta_pendiente(self):
        with mock.patch('cuentas.servicios.correo.send_mail', side_effect=SMTPException('sin servicio')):
            respuesta = self.client.post(self.url, datos_cliente(), follow=True)
        self.assertContains(respuesta, 'No se pudo enviar el correo')
        self.assertContains(respuesta, 'Reenviar correo')
        usuario = Usuario.objects.get(correo='ana@ejemplo.com')
        self.assertFalse(usuario.is_active)
        self.assertEqual(usuario.estado, 'Pendiente de verificación')

    def test_fallo_de_base_de_datos_no_deja_registros_incompletos(self):
        with mock.patch('cuentas.servicios.registro.generar_enlace', side_effect=DatabaseError('caída')):
            respuesta = self.client.post(self.url, datos_empresa())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Intenta más tarde')
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Empresa.objects.count(), 0)
        self.assertEqual(EnlaceVerificacion.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
