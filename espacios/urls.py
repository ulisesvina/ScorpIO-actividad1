from django.urls import path

from . import views, views_catalogo

app_name = 'espacios'

urlpatterns = [
    path('', views.mis_espacios, name='mis_espacios'),
    path('buscar/', views_catalogo.buscar_espacios, name='buscar_espacios'),
    path('publicar/', views.formulario_espacio, name='formulario_espacio'),
    path('publicar/precio-y-horarios/', views.precio_y_horarios, name='precio_y_horarios'),
    path('publicar/revisar/', views.revisar_y_publicar, name='revisar_y_publicar'),
    path('publicar/cancelar/', views.cancelar, name='cancelar'),
    path('<int:id_espacio>/', views_catalogo.detalle_espacio, name='detalle_espacio'),
    path('<int:id_espacio>/publicado/', views.espacio_publicado, name='espacio_publicado'),
    path('google-calendar/', views.vincular_calendario, name='vincular_calendario'),
]