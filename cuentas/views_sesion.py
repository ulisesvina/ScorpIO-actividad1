"""Vistas de inicio de sesión y pantalla de inicio (IniciarSesionController)."""
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from cuentas.forms_sesion import FormularioInicioSesion
from cuentas.servicios import autenticacion

logger = logging.getLogger(__name__)

MENSAJE_CREDENCIALES = 'Correo o contraseña incorrectos.'
MENSAJE_FALLO_GENERAL = 'Ocurrió un problema al iniciar sesión. Intenta más tarde.'


def _destino(request):
    """Adónde ir tras iniciar sesión: `next` solo si apunta a este mismo sitio."""
    siguiente = request.POST.get('next') or request.GET.get('next') or ''
    if siguiente and url_has_allowed_host_and_scheme(
        siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return siguiente
    return resolve_url(settings.LOGIN_REDIRECT_URL)


@sensitive_post_parameters('password')
@never_cache
@require_http_methods(['GET', 'POST'])
def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect(_destino(request))

    if request.method == 'POST':
        form = FormularioInicioSesion(request.POST)
        if form.is_valid():
            try:
                resultado = autenticacion.iniciar_sesion(
                    request, form.cleaned_data['correo'], form.cleaned_data['password'],
                )
            except DatabaseError:
                logger.exception('Error de base de datos al iniciar sesión')
                form.add_error(None, MENSAJE_FALLO_GENERAL)
            else:
                if resultado.resultado == autenticacion.OK:
                    return redirect(_destino(request))
                if resultado.resultado == autenticacion.PENDIENTE:
                    return render(request, 'cuentas/cuenta_pendiente.html', {
                        'correo': resultado.usuario.correo,
                    })
                form.add_error(None, MENSAJE_CREDENCIALES)
    else:
        form = FormularioInicioSesion()

    siguiente = request.POST.get('next') or request.GET.get('next') or ''
    return render(request, 'cuentas/iniciar_sesion.html', {'form': form, 'siguiente': siguiente})


@never_cache
@login_required
@require_GET
def inicio(request):
    return render(request, 'cuentas/inicio.html', {'usuario': request.user})
