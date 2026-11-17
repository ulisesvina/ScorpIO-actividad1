"""Modelos del caso de uso Publicar espacio

Corresponde con el diagrama de clases de Publicar espacio (y el general):
- Espacio           -> Espacio (idEspacio -> id; idEmpresa -> empresa)
- Fotografia        -> Fotografia (idFoto -> id; ubicacion -> archivo)
- Tarifa            -> Tarifa (precio, periodo)
- HorarioDisponible -> HorarioDisponible (dia, horaInicio, horaFin, disponible)
- EspacioBD / EspacioRepository / ConexionBD -> ORM de Django (igual que en cuentas)
"""
from django.core.validators import MinValueValidator
from django.db import models


class Espacio(models.Model):
    """Espacio que una Empresa registra y publica en Reserva-Hub"""

    PUBLICADO = 'publicado'
    ESTADOS = [
        (PUBLICADO, 'Publicado'),
    ]

    empresa = models.ForeignKey(
        'cuentas.Empresa', on_delete=models.CASCADE, related_name='espacios',
    )
    nombre = models.CharField('nombre del espacio', max_length=150)
    descripcion = models.TextField('descripción')
    capacidad = models.PositiveIntegerField('capacidad', validators=[MinValueValidator(1)])
    direccion = models.CharField('dirección', max_length=255)
    estado = models.CharField('estado', max_length=20, choices=ESTADOS)

    class Meta:
        verbose_name = 'espacio'
        verbose_name_plural = 'espacios'

    def __str__(self):
        return self.nombre

    def capturar_datos(self, datos, empresa):
        """ va a asignar  la información general capturada y la Empresa propietaria

        `datos` es un dict con: nombre, descripcion, capacidad y direccion
        no guarda en la base de datos
        """
        self.empresa = empresa
        self.nombre = datos['nombre']
        self.descripcion = datos['descripcion']
        self.capacidad = datos['capacidad']
        self.direccion = datos['direccion']
        return self

    def publicar(self):
        """marca el espacio como publicado para que los clientes puedan verlo"""
        self.estado = self.PUBLICADO


class Fotografia(models.Model):
    """imagen de un espacio. `archivo` guarda la ubicación dentro de MEDIA_ROOT"""

    FORMATOS_PERMITIDOS = ('JPEG', 'PNG')

    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='fotografias')
    nombre_archivo = models.CharField('nombre del archivo', max_length=255)
    archivo = models.ImageField('ubicación', upload_to='espacios/fotografias/')
    formato = models.CharField('formato', max_length=10)

    class Meta:
        verbose_name = 'fotografía'
        verbose_name_plural = 'fotografías'

    def __str__(self):
        return self.nombre_archivo

    def es_valida(self):
        return self.formato.upper() in self.FORMATOS_PERMITIDOS


class Tarifa(models.Model):
    """precio del espacio y periodo (modalidad) al que corresponde"""

    POR_HORA = 'hora'
    POR_DIA = 'dia'
    POR_SEMANA = 'semana'
    PERIODOS = [
        (POR_HORA, 'Por hora'),
        (POR_DIA, 'Por día'),
        (POR_SEMANA, 'Por semana'),
    ]

    espacio = models.OneToOneField(Espacio, on_delete=models.CASCADE, related_name='tarifa')
    precio = models.DecimalField('precio (MXN)', max_digits=10, decimal_places=2)
    periodo = models.CharField('modalidad de tarifa', max_length=10, choices=PERIODOS)

    class Meta:
        verbose_name = 'tarifa'
        verbose_name_plural = 'tarifas'

    def __str__(self):
        return '$%s / %s' % (self.precio, self.get_periodo_display().lower())

    def es_valida(self):
        periodos = [clave for clave, _ in self.PERIODOS]
        return self.precio is not None and self.precio > 0 and self.periodo in periodos


class HorarioDisponible(models.Model):
    """horario semanal en que el espacio se puede reservar"""

    DIAS = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
        ('domingo', 'Domingo'),
    ]

    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='horarios')
    dia = models.CharField('día', max_length=10, choices=DIAS)
    hora_inicio = models.TimeField('hora inicial')
    hora_fin = models.TimeField('hora final')
    disponible = models.BooleanField('disponible', default=True)

    class Meta:
        verbose_name = 'horario disponible'
        verbose_name_plural = 'horarios disponibles'

    def __str__(self):
        return '%s %s–%s' % (
            self.get_dia_display(), self.hora_inicio.strftime('%H:%M'), self.hora_fin.strftime('%H:%M'),
        )

    def es_valido(self):
        """la hora final debe ser posterior a la inicial (A4)"""
        return self.hora_inicio is not None and self.hora_fin is not None and self.hora_fin > self.hora_inicio

    def se_superpone_con(self, otro):
        """True si ambos horarios caen el mismo día y sus intervalos se cruzan (A4)"""
        return (
            self.dia == otro.dia
            and self.hora_inicio < otro.hora_fin
            and otro.hora_inicio < self.hora_fin
        )
