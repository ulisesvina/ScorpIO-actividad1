from django.urls import path

from . import views

app_name = 'cuentas'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('confirma-tu-correo/', views.confirma_correo, name='confirma_correo'),
    path('verificar/<str:token>/', views.verificar, name='verificar'),
    path('reenviar-correo/', views.reenviar_correo, name='reenviar_correo'),
    # PROVISIONAL: se reemplaza al implementar el caso de uso Iniciar sesión.
    path('iniciar-sesion/', views.iniciar_sesion, name='iniciar_sesion'),
]
