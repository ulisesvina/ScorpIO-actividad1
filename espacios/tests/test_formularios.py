"""Pruebas de los formularios de Publicar espacio (casos de prueba A-1 a A-8)."""
import io
from datetime import time
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from espacios.forms import ConjuntoHorarios, FormularioEspacio, FormularioPrecioYHorarios


def imagen(nombre='sala.png', formato='PNG'):
    """Imagen real de 1x1 píxel en el formato indicado."""
    contenido = io.BytesIO()
    Image.new('RGB', (1, 1)).save(contenido, formato)
    return SimpleUploadedFile(nombre, contenido.getvalue())


DATOS_GENERALES = {
    'nombre': 'Sala de juntas Central',
    'descripcion': 'Espacio equipado para reuniones',
    'capacidad': '10',
    'direccion': 'Av. Reforma 123',
}


def formulario_espacio(datos=None, fotos=None, previas=0):
    archivos = {'fotografias': fotos} if fotos is not None else {}
    return FormularioEspacio(
        {**DATOS_GENERALES, **(datos or {})}, archivos, fotografias_previas=previas,
    )


class FormularioEspacioTests(SimpleTestCase):
    def test_datos_validos(self):
        form = formulario_espacio(fotos=[imagen()])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.datos_generales()['capacidad'], 10)
        [(archivo, formato)] = form.cleaned_data['fotografias']
        self.assertEqual(formato, 'PNG')

    def test_acepta_jpeg(self):
        form = formulario_espacio(fotos=[imagen('sala.jpg', 'JPEG')])
        self.assertTrue(form.is_valid(), form.errors)

    def test_nombre_vacio_a1(self):
        form = formulario_espacio({'nombre': ''}, fotos=[imagen()])
        self.assertEqual(form.errors['nombre'], ['Ingrese el nombre del espacio'])

    def test_descripcion_vacia_a2(self):
        form = formulario_espacio({'descripcion': ''}, fotos=[imagen()])
        self.assertEqual(form.errors['descripcion'], ['Ingrese una descripción del espacio'])

    def test_sin_fotografias_a3(self):
        form = formulario_espacio(fotos=[])
        self.assertEqual(form.errors['fotografias'], ['Agregue al menos una fotografía'])

    def test_fotografias_de_un_envio_anterior_cuentan(self):
        form = formulario_espacio(fotos=[], previas=2)
        self.assertTrue(form.is_valid(), form.errors)

    def test_capacidad_cero_a4(self):
        form = formulario_espacio({'capacidad': '0'}, fotos=[imagen()])
        self.assertEqual(form.errors['capacidad'], ['La capacidad debe ser mayor que cero'])

    def test_direccion_vacia_a5(self):
        form = formulario_espacio({'direccion': ''}, fotos=[imagen()])
        self.assertEqual(form.errors['direccion'], ['Ingrese la ubicación del espacio'])

    def test_formato_no_permitido(self):
        form = formulario_espacio(fotos=[imagen('animacion.gif', 'GIF')])
        self.assertEqual(
            form.errors['fotografias'],
            ['No fue posible agregar una o más imágenes. Verifique el formato de los archivos'],
        )

    def test_archivo_que_no_es_imagen(self):
        falsa = SimpleUploadedFile('sala.jpg', b'esto no es una imagen')
        form = formulario_espacio(fotos=[falsa])
        self.assertIn('fotografias', form.errors)


class FormularioPrecioYHorariosTests(SimpleTestCase):
    def test_datos_validos(self):
        form = FormularioPrecioYHorarios({'precio': '350', 'periodo': 'hora'})
        self.assertTrue(form.is_valid(), form.errors)
        tarifa = form.tarifa()
        self.assertEqual(tarifa.precio, Decimal('350'))
        self.assertEqual(tarifa.periodo, 'hora')

    def test_precio_cero_o_negativo_a6(self):
        for precio in ('0', '-10'):
            form = FormularioPrecioYHorarios({'precio': precio, 'periodo': 'hora'})
            self.assertEqual(form.errors['precio'], ['El precio debe ser mayor que cero'])

    def test_sin_modalidad_a7(self):
        form = FormularioPrecioYHorarios({'precio': '350', 'periodo': ''})
        self.assertEqual(form.errors['periodo'], ['Seleccione un periodo de reservación'])


def conjunto(*filas, eliminar=()):
    datos = {
        'form-TOTAL_FORMS': str(len(filas)),
        'form-INITIAL_FORMS': str(len(filas)),
    }
    for i, (dia, inicio, fin) in enumerate(filas):
        datos.update({
            'form-%d-dia' % i: dia,
            'form-%d-hora_inicio' % i: inicio,
            'form-%d-hora_fin' % i: fin,
            'form-%d-disponible' % i: 'on',
        })
        if i in eliminar:
            datos['form-%d-DELETE' % i] = 'on'
    return ConjuntoHorarios(datos)


class ConjuntoHorariosTests(SimpleTestCase):
    def test_horarios_validos(self):
        horarios = conjunto(('lunes', '09:00', '18:00'), ('martes', '09:00', '18:00'))
        self.assertTrue(horarios.is_valid(), horarios.non_form_errors())
        lunes, martes = horarios.horarios()
        self.assertEqual((lunes.dia, lunes.hora_inicio, lunes.hora_fin), ('lunes', time(9), time(18)))
        self.assertTrue(lunes.disponible)

    def test_hora_final_anterior_a8(self):
        horarios = conjunto(('lunes', '18:00', '09:00'))
        self.assertFalse(horarios.is_valid())
        self.assertEqual(horarios.non_form_errors(), ['Verifique los horarios ingresados'])
        self.assertTrue(horarios.forms[0].con_error)

    def test_horarios_repetidos(self):
        horarios = conjunto(('martes', '09:00', '18:00'), ('martes', '09:00', '18:00'))
        self.assertFalse(horarios.is_valid())
        self.assertTrue(horarios.forms[0].con_error and horarios.forms[1].con_error)

    def test_sin_horarios(self):
        horarios = conjunto()
        self.assertFalse(horarios.is_valid())
        self.assertEqual(horarios.non_form_errors(), ['Verifique los horarios ingresados'])

    def test_fila_eliminada_no_cuenta(self):
        horarios = conjunto(('martes', '09:00', '18:00'), ('martes', '09:00', '18:00'), eliminar=(1,))
        self.assertTrue(horarios.is_valid(), horarios.non_form_errors())
        self.assertEqual(len(horarios.horarios()), 1)

    def test_hora_vacia(self):
        horarios = conjunto(('lunes', '', '18:00'))
        self.assertFalse(horarios.is_valid())
        self.assertEqual(horarios.non_form_errors(), ['Verifique los horarios ingresados'])
