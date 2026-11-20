"""Vistas del registro y la verificación de correo (UsuarioController)."""
import logging

from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from cuentas.forms import FormularioRegistro, FormularioReenvio
from cuentas.servicios import registro as servicio_registro
from cuentas.servicios import verificacion

logger = logging.getLogger(__name__)

SESION_CORREO = 'correo_pendiente'
SESION_ENVIADO = 'correo_enviado'

MENSAJE_FALLO_GENERAL = 'Ocurrió un problema al guardar tu registro. Intenta más tarde.'


@require_http_methods(['GET', 'POST'])
def registro(request):
    if request.method == 'POST':
        form = FormularioRegistro(request.POST)
        if form.is_valid():
            try:
                resultado = servicio_registro.registrar(form.datos_de_registro(), request)
            except servicio_registro.CorreoYaRegistrado:
                form.correo_ya_activo = True
                form.add_error('correo', 'Ya existe una cuenta con ese correo electrónico.')
            except DatabaseError:
                logger.exception('Error de base de datos durante el registro')
                form.add_error(None, MENSAJE_FALLO_GENERAL)
            else:
                request.session[SESION_CORREO] = resultado.usuario.correo
                request.session[SESION_ENVIADO] = resultado.correo_enviado
                return redirect('cuentas:confirma_correo')
    else:
        form = FormularioRegistro()
    return render(request, 'cuentas/registro.html', {'form': form})


@require_GET
def confirma_correo(request):
    correo = request.session.get(SESION_CORREO)
    if not correo:
        return redirect('cuentas:registro')
    return render(request, 'cuentas/confirma_correo.html', {
        'correo': correo,
        'enviado': request.session.get(SESION_ENVIADO, False),
    })


@never_cache
@require_GET
def verificar(request, token):
    resultado, usuario = verificacion.activar_cuenta(token)
    estados = {
        verificacion.ACTIVADA: ('cuentas/correo_verificado.html', 200),
        verificacion.EXPIRADO: ('cuentas/enlace_problema.html', 410),
        verificacion.USADO: ('cuentas/enlace_problema.html', 410),
        verificacion.INVALIDO: ('cuentas/enlace_problema.html', 404),
    }
    plantilla, codigo = estados[resultado]
    respuesta = render(request, plantilla, {'resultado': resultado, 'usuario': usuario}, status=codigo)
    respuesta['Referrer-Policy'] = 'no-referrer'  # el token viaja en la URL
    return respuesta


@require_http_methods(['GET', 'POST'])
def reenviar_correo(request):
    if request.method == 'POST':
        form = FormularioReenvio(request.POST)
        if form.is_valid():
            try:
                servicio_registro.reenviar(form.cleaned_data['correo'], request)
            except DatabaseError:
                logger.exception('Error de base de datos al reenviar el correo de verificación')
                form.add_error(None, MENSAJE_FALLO_GENERAL)
            else:
                # Respuesta idéntica exista o no la cuenta, para no revelar correos.
                request.session[SESION_CORREO] = form.cleaned_data['correo']
                request.session[SESION_ENVIADO] = True
                return redirect('cuentas:confirma_correo')
    else:
        form = FormularioReenvio(initial={'correo': request.session.get(SESION_CORREO, '')})
    return render(request, 'cuentas/reenviar_correo.html', {'form': form})

