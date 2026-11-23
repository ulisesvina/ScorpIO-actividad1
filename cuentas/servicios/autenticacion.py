"""AutenticacionService: verifica credenciales y crea la sesión (caso de uso Iniciar sesión)."""
from collections import namedtuple

from django.contrib.auth import login
from django.contrib.auth.hashers import make_password

from cuentas.models import Usuario

BACKEND = 'django.contrib.auth.backends.ModelBackend'

# Resultados posibles.
OK = 'ok'
PENDIENTE = 'pendiente'            # credenciales correctas, correo sin verificar (A3)
CREDENCIALES_INVALIDAS = 'invalidas'  # A2: no se distingue qué dato falló

ResultadoAutenticacion = namedtuple('ResultadoAutenticacion', 'resultado usuario')


def verificar_credenciales(correo, password):
    """Comprueba correo y contraseña sin crear sesión.

    No usa `authenticate()` porque este descarta las cuentas inactivas sin
    distinguir el motivo, y aquí hay que separar «pendiente de verificación»
    de «contraseña incorrecta».
    """
    usuario = Usuario.objects.filter(correo=correo).first()
    if usuario is None:
        # Hash de relleno: el tiempo de respuesta no debe revelar si el correo existe.
        make_password(password)
        return ResultadoAutenticacion(CREDENCIALES_INVALIDAS, None)
    if not usuario.check_password(password):
        return ResultadoAutenticacion(CREDENCIALES_INVALIDAS, None)
    if usuario.is_active:
        return ResultadoAutenticacion(OK, usuario)
    if usuario.correo_verificado_en is None:
        return ResultadoAutenticacion(PENDIENTE, usuario)
    # Verificada pero desactivada: la especificación no la contempla; se trata
    # como credenciales incorrectas para no dar pistas.
    return ResultadoAutenticacion(CREDENCIALES_INVALIDAS, None)


def iniciar_sesion(request, correo, password):
    """Verifica las credenciales y, si son válidas y la cuenta está activa, crea la sesión."""
    resultado = verificar_credenciales(correo, password)
    if resultado.resultado == OK:
        # login() renueva la clave de sesión (evita fijación de sesión).
        login(request, resultado.usuario, backend=BACKEND)
    return resultado
