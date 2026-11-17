"""RegistrarUsuarioService: coordina la creación de la cuenta y el envío del enlace."""
from collections import namedtuple

from django.db import IntegrityError, transaction

from cuentas.models import Empresa, Usuario
from cuentas.servicios import correo as servicio_correo
from cuentas.servicios.verificacion import generar_enlace

ResultadoRegistro = namedtuple('ResultadoRegistro', 'usuario correo_enviado')


class CorreoYaRegistrado(Exception):
    """El correo pertenece a una cuenta que ya está activa."""


def _aplicar_datos(usuario, datos):
    usuario.nombre = datos['nombre']
    usuario.es_empresa = datos['es_empresa']
    usuario.set_password(datos['password'])
    usuario.save()
    if datos['es_empresa']:
        Empresa.objects.update_or_create(usuario=usuario, defaults={'rfc': datos['rfc']})
    else:
        Empresa.objects.filter(usuario=usuario).delete()


def registrar(datos, request):
    """Registra (o re-registra, si estaba pendiente) la cuenta y envía el enlace.

    `datos` es un dict con: nombre, correo, password, es_empresa y rfc.
    Si la base de datos falla, la transacción se revierte y no queda nada a medias.
    Si el correo falla, la cuenta queda pendiente de verificación.
    """
    try:
        with transaction.atomic():
            usuario = Usuario.objects.select_for_update().filter(correo=datos['correo']).first()
            if usuario is not None and usuario.is_active:
                raise CorreoYaRegistrado()
            if usuario is None:
                usuario = Usuario(correo=datos['correo'])
            # Una cuenta pendiente se reescribe con los datos del último envío: así
            # nadie puede "reservar" el correo de otra persona con una contraseña
            # que luego quedaría activa al verificarse.
            _aplicar_datos(usuario, datos)
            _enlace, token = generar_enlace(usuario)
    except IntegrityError:
        raise CorreoYaRegistrado()

    enviado = servicio_correo.enviar_enlace(usuario, token, request)
    return ResultadoRegistro(usuario, enviado)


def reenviar(correo, request):
    """Reenvía el enlace si hay una cuenta pendiente con ese correo.

    No revela si el correo existe: devuelve True solo para uso interno/pruebas.
    """
    usuario = Usuario.objects.filter(correo=correo, is_active=False).first()
    if usuario is None:
        return False
    with transaction.atomic():
        _enlace, token = generar_enlace(usuario)
    return servicio_correo.enviar_enlace(usuario, token, request)
