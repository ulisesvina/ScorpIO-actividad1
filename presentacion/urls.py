from django.urls import path

from . import views

urlpatterns = [
    path("belen/", views.pagina_belen, name="pagina_belen"),
]
urlpatterns = [
    path('belen/', views.presentacion_belen, name='presentacion_belen'),   # ya existente, no borrar
    path('tunombre/', views.presentacion_tunombre, name='presentacion_tunombre'),
]