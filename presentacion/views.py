from django.http import HttpResponse


def pagina_belen(request):
    return HttpResponse(
        "<h1>Belén</h1>"
        "<p>Rol en ScorpIO: Responsable y Colaboración</p>"
    )

def pagina_eduardo(request):
    return HttpResponse(
        "<h1>Eduardo</h1>"
        "<p>Rol en ScorpIO: Responsable de calidad </p>"
    )
