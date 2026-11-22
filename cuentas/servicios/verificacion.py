"""Generación y validación de enlaces de verificación de correo.

El token que viaja en el correo se genera con `secrets` y NUNCA se guarda:
en la base de datos solo queda su hash SHA-256.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from cuentas.models import EnlaceVerificacion

# Resultados posibles al abrir un enlace.
ACTIVADA = 'activada'
EXPIRADO = 'expirado'
USADO = 'usado'
INVALIDO = 'invalido'

LONGITUD_MAXIMA_TOKEN = 128


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def horas_de_vigencia():
    return getattr(settings, 'VERIFICACION_CORREO_HORAS', 24)


def generar_enlace(usuario):
    """Crea un enlace nuevo e invalida los pendientes del usuario.

    Devuelve (enlace, token_plano). El token plano solo debe usarse para armar
    la URL del correo.
    """
    EnlaceVerificacion.objects.filter(usuario=usuario, usado_en__isnull=True).delete()
    token = secrets.token_urlsafe(32)
    enlace = EnlaceVerificacion.objects.create(
        usuario=usuario,
        token_hash=_hash(token),
        expira_en=timezone.now() + timedelta(hours=horas_de_vigencia()),
    )
    return enlace, token


def activar_cuenta(token):
    """Valida el token y, si procede, activa la cuenta.

    Devuelve (resultado, usuario). `usuario` es None cuando el token es inválido.
    """
    if not token or len(token) > LONGITUD_MAXIMA_TOKEN:
        return INVALIDO, None

    with transaction.atomic():
        enlace = (
            EnlaceVerificacion.objects.select_for_update()
            .select_related('usuario')
            .filter(token_hash=_hash(token))
            .first()
        )
        if enlace is None:
            return INVALIDO, None

        usuario = enlace.usuario
        if enlace.usado_en is not None:
            return USADO, usuario
        ahora = timezone.now()
        if enlace.expira_en <= ahora:
            return EXPIRADO, usuario

        usuario.is_active = True
        usuario.correo_verificado_en = ahora
        usuario.save(update_fields=['is_active', 'correo_verificado_en'])
        enlace.usado_en = ahora
        enlace.save(update_fields=['usado_en'])
        return ACTIVADA, usuario
