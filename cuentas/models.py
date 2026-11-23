"""Modelos del caso de uso Registrar Usuario.

Correspondencia con el diagrama de clases:
- Usuario            -> Usuario (esEmpresa, cuentaActiva -> is_active + correo_verificado_en)
- Empresa            -> Empresa (solo RFC; idCalendario se pospone a Google Calendar)
- EnlaceVerificacion -> EnlaceVerificacion (absorbe TokenVerificacion)
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    """Administrador de usuarios que identifica a las personas por su correo."""

    def _crear(self, correo, password, **extra):
        if not correo:
            raise ValueError('El correo electrónico es obligatorio.')
        correo = self.normalize_email(correo).lower()
        usuario = self.model(correo=correo, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_active', True)
        extra.setdefault('correo_verificado_en', timezone.now())
        if not extra['is_staff'] or not extra['is_superuser']:
            raise ValueError('Un superusuario debe tener is_staff e is_superuser en True.')
        return self._crear(correo, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Cuenta de la plataforma. Es Cliente salvo que `es_empresa` sea True.

    Una cuenta nace con is_active=False (Pendiente de verificación) y solo pasa
    a Activa cuando se abre el enlace enviado a su correo.
    """

    correo = models.EmailField('correo electrónico', max_length=254, unique=True)
    nombre = models.CharField('nombre', max_length=150)
    es_empresa = models.BooleanField('es empresa', default=False)
    is_active = models.BooleanField('activa', default=False)
    is_staff = models.BooleanField('acceso al panel de administración', default=False)
    correo_verificado_en = models.DateTimeField('correo verificado en', null=True, blank=True)
    fecha_registro = models.DateTimeField('fecha de registro', default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = 'correo'
    EMAIL_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return self.correo

    @property
    def estado(self):
        if self.is_active and self.correo_verificado_en is not None:
            return 'Activa'
        return 'Pendiente de verificación'

    @property
    def tipo_cuenta(self):
        return 'Empresa' if self.es_empresa else 'Cliente'


class Empresa(models.Model):
    """Datos propios de una cuenta de tipo Empresa (solo el RFC por ahora)."""

    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name='empresa',
    )
    rfc = models.CharField('RFC o registro fiscal', max_length=13)

    class Meta:
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return '%s (%s)' % (self.usuario.nombre, self.rfc)


class EnlaceVerificacion(models.Model):
    """Enlace de confirmación de correo. Solo se guarda el hash del token."""

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='enlaces_verificacion',
    )
    token_hash = models.CharField(max_length=64, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'enlace de verificación'
        verbose_name_plural = 'enlaces de verificación'

    def esta_vigente(self):
        return self.usado_en is None and self.expira_en > timezone.now()
