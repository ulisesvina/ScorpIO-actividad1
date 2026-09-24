from django.http import HttpResponse


def pagina_belen(request):
    return HttpResponse(
        "<h1>Belén</h1>"
        "<p>Rol en ScorpIO: Responsable y Colaboración</p>"
    )
