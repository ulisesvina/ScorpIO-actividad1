from django.urls import path

from . import views, views_sesion, views_cierre

app_name = 'cuentas'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('confirma-tu-correo/', views.confirma_correo, name='confirma_correo'),
    path('verificar/<str:token>/', views.verificar, name='verificar'),
    path('reenviar-correo/', views.reenviar_correo, name='reenviar_correo'),
    path('iniciar-sesion/', views_sesion.iniciar_sesion, name='iniciar_sesion'),
    path('inicio/', views_sesion.inicio, name='inicio'),
    path('cerrar-sesion/', views_cierre.cerrar_sesion, name='cerrar_sesion'),
]
