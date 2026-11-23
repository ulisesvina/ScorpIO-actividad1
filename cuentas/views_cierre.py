"""Vista de Cerrar sesión (CerrarSesionController)."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import redirect
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_POST

from cuentas.middleware import COOKIE_CIERRE, MENSAJE_OTRA_VENTANA, SEGUNDOS_COOKIE_CIERRE

logger = logging.getLogger(__name__)

MENSAJE_ERROR_SERVIDOR = 'Ocurrió un error en el servidor, pero tu sesión local ha sido cerrada.'


@require_POST
def cerrar_sesion(request):
    respuesta = redirect('cuentas:iniciar_sesion')

    if request.user.is_authenticated:
        try:
            logout(request)  # revoca la sesión en el servidor y borra la cookie
        except Exception:  # E2: falla interna al revocar
            logger.exception('Falló la revocación de la sesión')
            request.user = AnonymousUser()
            request.session.modified = False  # que SessionMiddleware no la vuelva a guardar
            respuesta.delete_cookie(
                settings.SESSION_COOKIE_NAME,
                path=settings.SESSION_COOKIE_PATH, domain=settings.SESSION_COOKIE_DOMAIN,
            )
            messages.error(request, MENSAJE_ERROR_SERVIDOR)
        respuesta.set_cookie(COOKIE_CIERRE, '1', max_age=SEGUNDOS_COOKIE_CIERRE, samesite='Lax')
    elif COOKIE_CIERRE in request.COOKIES:
        # Ya la cerraron en otra pestaña y aquí presionaron «Cerrar sesión» (A2).
        messages.info(request, MENSAJE_OTRA_VENTANA)

    add_never_cache_headers(respuesta)
    return respuesta