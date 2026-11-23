"""ServicioCorreo: envío del correo con el enlace de verificación."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from cuentas.servicios.verificacion import horas_de_vigencia

logger = logging.getLogger(__name__)

ASUNTO = 'Confirma tu correo en Reserva-Hub'


def enviar_enlace(usuario, token, request):
    """Envía el enlace de verificación. Devuelve True si el envío tuvo éxito.

    Nunca lanza excepciones de correo: si algo falla devuelve False para que
    el flujo deje la cuenta pendiente (E2). No se registra el token.
    """
    url = request.build_absolute_uri(reverse('cuentas:verificar', args=[token]))
    cuerpo = render_to_string('cuentas/correo_verificacion.txt', {
        'usuario': usuario,
        'url': url,
        'horas': horas_de_vigencia(),
    })
    try:
        send_mail(ASUNTO, cuerpo, settings.DEFAULT_FROM_EMAIL, [usuario.correo], fail_silently=False)
    except Exception:  # SMTPException, OSError, etc.
        logger.exception('Falló el envío del correo de verificación (usuario id=%s)', usuario.pk)
        return False
    return True
