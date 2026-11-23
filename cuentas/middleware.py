"""ControlSesionMiddleware: inactividad (A1), cierre en otra ventana (A2) y sin caché (A3)."""
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, resolve_url
from django.utils.cache import add_never_cache_headers

CLAVE_ACTIVIDAD = 'ultima_actividad'
COOKIE_CIERRE = 'rh_sesion_cerrada'   # la pone «Cerrar sesión»; dura pocos minutos
SEGUNDOS_COOKIE_CIERRE = 300
INTERVALO_ACTUALIZACION = 60          # evita escribir la sesión en cada petición

MENSAJE_EXPIRADA = 'Tu sesión ha expirado. Por favor, inicia sesión nuevamente.'
MENSAJE_OTRA_VENTANA = 'La sesión ha sido finalizada en otra ventana.'


def segundos_de_inactividad():
    return getattr(settings, 'SESION_INACTIVIDAD_SEGUNDOS', 1800)


class ControlSesionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mostrar_otra_ventana = False

        if request.user.is_authenticated:
            ahora = time.time()
            ultima = request.session.get(CLAVE_ACTIVIDAD)
            if ultima is not None and ahora - ultima > segundos_de_inactividad():
                # A1: la sesión caducó por inactividad.
                logout(request)
                messages.warning(request, MENSAJE_EXPIRADA)
                if request.method == 'GET':
                    return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))
                return redirect(settings.LOGIN_URL)
            if ultima is None or ahora - ultima > INTERVALO_ACTUALIZACION:
                request.session[CLAVE_ACTIVIDAD] = ahora
        elif (
            request.method == 'GET'
            and 'next' in request.GET
            and COOKIE_CIERRE in request.COOKIES
            and request.path == resolve_url(settings.LOGIN_URL)
        ):
            # A2: llegó al login desde una página privada justo después de cerrar sesión
            # (las pestañas comparten cookies).
            messages.info(request, MENSAJE_OTRA_VENTANA)
            mostrar_otra_ventana = True

        respuesta = self.get_response(request)

        if request.user.is_authenticated and respuesta.get('Content-Type', '').startswith('text/html'):
            add_never_cache_headers(respuesta)  # A3: sin caché para el botón «Atrás»
        if (request.user.is_authenticated or mostrar_otra_ventana) and COOKIE_CIERRE in request.COOKIES:
            respuesta.delete_cookie(COOKIE_CIERRE)
        return respuesta