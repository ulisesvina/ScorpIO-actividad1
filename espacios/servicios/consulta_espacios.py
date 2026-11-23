"""ConsultaEspaciosService: búsqueda y detalle de espacios publicados (caso de uso Ver espacio)."""
from django.db.models import Q

from espacios.models import Espacio, HorarioDisponible

DIAS = [clave for clave, _ in HorarioDisponible.DIAS]  # lunes ... domingo, en orden


class EspacioNoDisponible(Exception):
    """El espacio no existe o ya no está publicado (A3)."""


def espacios_publicados():
    return (
        Espacio.objects.filter(estado=Espacio.PUBLICADO)
        .select_related('tarifa', 'empresa__usuario')
        .prefetch_related('fotografias')
        .order_by('-id')
    )


def buscar(q='', ubicacion='', fecha=None):
    """Lista de espacios publicados que cumplen los filtros (A1). Sin filtros, todos."""
    espacios = espacios_publicados()
    if q:
        espacios = espacios.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    if ubicacion:
        espacios = espacios.filter(direccion__icontains=ubicacion)
    if fecha:
        # Los horarios son semanales: la fecha se traduce a su día de la semana.
        espacios = espacios.filter(
            horarios__dia=DIAS[fecha.weekday()], horarios__disponible=True,
        ).distinct()
    return list(espacios)


def obtener_publicado(id_espacio):
    try:
        return espacios_publicados().prefetch_related('horarios').get(pk=id_espacio)
    except Espacio.DoesNotExist:
        raise EspacioNoDisponible()


def horarios_disponibles(espacio):
    """Horarios que sí se pueden reservar (no desactivados ni ocupados en Google Calendar)."""
    orden = {dia: i for i, dia in enumerate(DIAS)}
    libres = [h for h in espacio.horarios.all() if h.disponible]
    return sorted(libres, key=lambda h: (orden.get(h.dia, len(DIAS)), h.hora_inicio))