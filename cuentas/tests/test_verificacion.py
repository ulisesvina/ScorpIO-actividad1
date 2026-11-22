from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cuentas.models import EnlaceVerificacion, Usuario
from cuentas.servicios.verificacion import generar_enlace

CLAVE = 'Reserva2026-Hub'


def crear_pendiente(correo='ana@ejemplo.com'):
    usuario = Usuario.objects.create_user(correo, CLAVE, nombre='Ana Pérez')
    enlace, token = generar_enlace(usuario)
    return usuario, enlace, token


def url_verificar(token):
    return reverse('cuentas:verificar', args=[token])


class ActivacionTests(TestCase):
    def test_enlace_valido_activa_la_cuenta(self):
        usuario, enlace, token = crear_pendiente()
        respuesta = self.client.get(url_verificar(token))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo verificado')
        usuario.refresh_from_db()
        enlace.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertIsNotNone(usuario.correo_verificado_en)
        self.assertEqual(usuario.estado, 'Activa')
        self.assertIsNotNone(enlace.usado_en)

    def test_el_token_no_se_guarda_en_claro(self):
        _usuario, enlace, token = crear_pendiente()
        self.assertNotEqual(enlace.token_hash, token)
        self.assertFalse(EnlaceVerificacion.objects.filter(token_hash=token).exists())

    def test_token_invalido(self):
        usuario, _enlace, _token = crear_pendiente()
        respuesta = self.client.get(url_verificar('token-que-no-existe'))
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, 'no es válido', status_code=404)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_token_expirado(self):
        usuario, enlace, token = crear_pendiente()
        enlace.expira_en = timezone.now() - timedelta(minutes=1)
        enlace.save()
        respuesta = self.client.get(url_verificar(token))
        self.assertEqual(respuesta.status_code, 410)
        self.assertContains(respuesta, 'Enlace vencido', status_code=410)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertIsNone(usuario.correo_verificado_en)

    def test_reutilizacion_del_enlace(self):
        usuario, _enlace, token = crear_pendiente()
        self.assertEqual(self.client.get(url_verificar(token)).status_code, 200)
        usuario.refresh_from_db()
        primera_vez = usuario.correo_verificado_en
        respuesta = self.client.get(url_verificar(token))
        self.assertEqual(respuesta.status_code, 410)
        self.assertContains(respuesta, 'ya utilizado', status_code=410)
        usuario.refresh_from_db()
        self.assertEqual(usuario.correo_verificado_en, primera_vez)

    def test_la_activacion_solo_acepta_get(self):
        usuario, _enlace, token = crear_pendiente()
        self.assertEqual(self.client.post(url_verificar(token)).status_code, 405)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_la_respuesta_no_envia_referrer_y_no_se_cachea(self):
        _usuario, _enlace, token = crear_pendiente()
        respuesta = self.client.get(url_verificar(token))
        self.assertEqual(respuesta['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-cache', respuesta['Cache-Control'])

    @override_settings(VERIFICACION_CORREO_HORAS=2)
    def test_la_vigencia_es_configurable(self):
        _usuario, enlace, _token = crear_pendiente()
        esperado = timezone.now() + timedelta(hours=2)
        self.assertLess(abs(enlace.expira_en - esperado), timedelta(minutes=1))
        self.assertTrue(enlace.esta_vigente())


class ReenvioTests(TestCase):
    url = reverse('cuentas:reenviar_correo')

    def test_reenvio_invalida_el_enlace_anterior(self):
        _usuario, _enlace, token_viejo = crear_pendiente()
        self.client.post(self.url, {'correo': 'ana@ejemplo.com'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(url_verificar(token_viejo)).status_code, 404)
        token_nuevo = mail.outbox[0].body.split('/cuentas/verificar/')[1].split('/')[0]
        self.assertEqual(self.client.get(url_verificar(token_nuevo)).status_code, 200)

    def test_reenvio_tras_enlace_vencido(self):
        usuario, enlace, token = crear_pendiente()
        enlace.expira_en = timezone.now() - timedelta(minutes=1)
        enlace.save()
        self.assertEqual(self.client.get(url_verificar(token)).status_code, 410)
        self.client.post(self.url, {'correo': usuario.correo})
        self.assertEqual(len(mail.outbox), 1)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_respuesta_identica_si_el_correo_no_existe(self):
        respuesta = self.client.post(self.url, {'correo': 'nadie@ejemplo.com'}, follow=True)
        self.assertContains(respuesta, 'Confirma tu correo')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_reenvia_a_cuentas_ya_activas(self):
        Usuario.objects.create_user('ana@ejemplo.com', CLAVE, nombre='Ana', is_active=True)
        self.client.post(self.url, {'correo': 'ana@ejemplo.com'})
        self.assertEqual(len(mail.outbox), 0)
