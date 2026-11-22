from django.contrib import admin

from .models import Empresa, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """Consulta de cuentas. No permite crear usuarios desde aquí (la contraseña
    se guardaría sin hash); para el primer administrador usa `createsuperuser`."""

    list_display = ('correo', 'nombre', 'es_empresa', 'is_active', 'correo_verificado_en', 'fecha_registro')
    list_filter = ('es_empresa', 'is_active')
    search_fields = ('correo', 'nombre')
    readonly_fields = ('password', 'last_login', 'fecha_registro')

    def has_add_permission(self, request):
        return False


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rfc')
    search_fields = ('rfc', 'usuario__correo')
