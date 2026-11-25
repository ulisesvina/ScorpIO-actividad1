"""Modelos del caso de uso Publicar espacio

Corresponde con el diagrama de clases de Publicar espacio (y el general):
- Espacio           -> Espacio (idEspacio -> id; idEmpresa -> empresa)
- Fotografia        -> Fotografia (idFoto -> id; ubicacion -> archivo)
- Tarifa            -> Tarifa (precio, periodo)
- HorarioDisponible -> HorarioDisponible (dia, horaInicio, horaFin, disponible)
- Reservacion       -> Reservacion (agregada por el caso de uso Editar espacio)
- EspacioBD / EspacioRepository / ConexionBD -> ORM de Django (igual que en cuentas)
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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
    # Agregado por el caso de uso Editar espacio (dimensionesM2). Opcional: los espacios
    # publicados antes no lo tienen y Publicar espacio no lo pide
    dimensiones_m2 = models.DecimalField(
        'dimensiones (m²)', max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
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

    # --- Editar espacio ---

    def pertenece_a(self, empresa):
        """True si el espacio es de la Empresa indicada (solo su dueña puede editarlo)"""
        return empresa is not None and self.empresa_id == empresa.pk

    def esta_disponible(self):
        """True si el espacio sigue publicado y, por lo tanto, se puede editar"""
        return self.estado == self.PUBLICADO

    def aplicar_cambios(self, datos):
        """asigna la información general editada; idEspacio e idEmpresa son inmutables

        `datos` es un dict con: nombre, descripcion, capacidad, direccion y (opcional)
        dimensiones_m2. No guarda en la base de datos
        """
        self.nombre = datos['nombre']
        self.descripcion = datos['descripcion']
        self.capacidad = datos['capacidad']
        self.direccion = datos['direccion']
        self.dimensiones_m2 = datos.get('dimensiones_m2')
        return self


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

    UNIDADES = {POR_HORA: 'hora', POR_DIA: 'día', POR_SEMANA: 'semana'}

    def __str__(self):
        """Como en los prototipos: «$350 / hora», «$1,800 / día», «$12,000 / semana»."""
        decimales = 0 if self.precio == self.precio.to_integral_value() else 2
        return '$%s / %s' % (format(self.precio, ',.%df' % decimales), self.UNIDADES.get(self.periodo, ''))

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


class Reservacion(models.Model):
    """Reservación de un espacio (1 Espacio tiene 0..* Reservaciones)

    La crea el caso de uso Reservar espacio; Editar espacio solo la consulta para no
    dejar fuera de capacidad u horario a las reservaciones vigentes
    """

    PENDIENTE = 'pendiente'
    CONFIRMADA = 'confirmada'
    CANCELADA = 'cancelada'
    FINALIZADA = 'finalizada'
    ESTADOS = [
        (PENDIENTE, 'Pendiente'),
        (CONFIRMADA, 'Confirmada'),
        (CANCELADA, 'Cancelada'),
        (FINALIZADA, 'Finalizada'),
    ]
    ESTADOS_VIGENTES = (PENDIENTE, CONFIRMADA)

    # Mismo orden que date.weekday(): lunes = 0 ... domingo = 6
    DIAS_SEMANA = [clave for clave, _ in HorarioDisponible.DIAS]

    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='reservaciones')
    inicio = models.DateTimeField('inicio')
    fin = models.DateTimeField('fin')
    cantidad_personas = models.PositiveIntegerField('cantidad de personas', validators=[MinValueValidator(1)])
    estado = models.CharField('estado', max_length=20, choices=ESTADOS, default=PENDIENTE)

    class Meta:
        verbose_name = 'reservación'
        verbose_name_plural = 'reservaciones'
        ordering = ['inicio']

    def __str__(self):
        inicio = timezone.localtime(self.inicio)
        fin = timezone.localtime(self.fin)
        return '%s %s–%s' % (inicio.strftime('%d/%m/%Y'), inicio.strftime('%H:%M'), fin.strftime('%H:%M'))

    def es_vigente(self, ahora=None):
        """True si no está cancelada ni finalizada y todavía no termina"""
        return self.estado in self.ESTADOS_VIGENTES and self.fin > (ahora or timezone.now())

    def es_compatible_con(self, datos):
        """True si la reservación cabe en los datos editados del espacio

        `datos` es un dict con `capacidad` y `horarios` (instancias de HorarioDisponible).
        Debe cumplir la capacidad y quedar completa dentro de un horario disponible
        del mismo día de la semana. Si falta alguno de los dos, esa parte no se revisa
        """
        capacidad = datos.get('capacidad')
        if capacidad is not None and self.cantidad_personas > capacidad:
            return False
        horarios = datos.get('horarios')
        return horarios is None or self.cabe_en_horarios(horarios)

    def cabe_en_horarios(self, horarios):
        """True si la reservación queda completa dentro de un horario disponible de su día"""
        inicio = timezone.localtime(self.inicio)
        fin = timezone.localtime(self.fin)
        if inicio.date() != fin.date():
            return False  # los horarios son por día: una reservación de varios días no cabe
        dia = self.DIAS_SEMANA[inicio.weekday()]
        return any(
            horario.disponible and horario.dia == dia
            and horario.hora_inicio <= inicio.time() and fin.time() <= horario.hora_fin
            for horario in horarios
        )
