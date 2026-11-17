from django.contrib import admin

from .models import Espacio, Fotografia, HorarioDisponible, Tarifa


class TarifaEnLinea(admin.StackedInline):
    model = Tarifa
    can_delete = False


class HorarioEnLinea(admin.TabularInline):
    model = HorarioDisponible
    extra = 0


class FotografiaEnLinea(admin.TabularInline):
    model = Fotografia
    extra = 0


@admin.register(Espacio)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'capacidad', 'direccion', 'estado')
    list_filter = ('estado',)
    search_fields = ('nombre', 'direccion', 'empresa__usuario__nombre')
    inlines = [TarifaEnLinea, HorarioEnLinea, FotografiaEnLinea]
