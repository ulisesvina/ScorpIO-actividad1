from django.urls import path

from . import views

urlpatterns = [
    path("belen/", views.pagina_belen, name="pagina_belen"),
]