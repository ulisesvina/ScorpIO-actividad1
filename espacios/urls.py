from django.urls import path

from . import views, views_catalogo, views_edicion

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
    path('<int:id_espacio>/editar/', views_edicion.abrir_edicion, name='abrir_edicion'),
    path('<int:id_espacio>/editar/informacion/', views_edicion.editar_informacion, name='editar_informacion'),
    path(
        '<int:id_espacio>/editar/precio-y-horarios/', views_edicion.editar_precio_y_horarios,
        name='editar_precio_y_horarios',
    ),
    path('<int:id_espacio>/editar/revisar/', views_edicion.revisar_y_guardar, name='revisar_y_guardar'),
    path('<int:id_espacio>/editar/cancelar/', views_edicion.cancelar_edicion, name='cancelar_edicion'),
    path('<int:id_espacio>/actualizado/', views_edicion.espacio_actualizado, name='espacio_actualizado'),
    path('google-calendar/', views.vincular_calendario, name='vincular_calendario'),
]