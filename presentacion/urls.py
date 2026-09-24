from django.urls import path

from . import views

urlpatterns = [
    path("belen/", views.pagina_belen, name="pagina_belen"),
    path("eduardo/", views.pagina_eduardo, name="pagina_eduardo"),
    path("tunombre/", views.presentacion_tunombre, name="presentacion_tunombre"),
]
