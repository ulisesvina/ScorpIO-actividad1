from django.http import HttpResponse


def pagina_belen(request):
    return HttpResponse(
        "<h1>Belén</h1>"
        "<p>Rol en ScorpIO: Responsable y Colaboración</p>"
    )
def presentacion_tunombre(request):
    html = """
    <html>
        <head><title>Página de presentación</title></head>
        <body>
            <h1>Emiliano</h1>
            <p>Rol en ScorpIO: Responsablel</p>
        </body>
    </html>
    """
    return HttpResponse(html)
