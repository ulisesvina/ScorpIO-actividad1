# ScorpIO actividad 1
## Requisitos

- Python 3.9
- Git.

## Instalación

Clona el repositorio y entra en la carpeta del proyecto:

```bash
git clone https://github.com/ulisesvina/ScorpIO-actividad1
cd ScorpIO-actividad1
```

Crea y activa el entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

En macOS o Linux con:

```sh
source .venv/bin/activate
```

En Windows, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecutar el servidor

Desde la carpeta raíz del proyecto y con el entorno virtual activo:

```bash
python manage.py migrate
python manage.py runserver
```

> **Si ya habías ejecutado `migrate` antes de esta versión**, borra tu `db.sqlite3` local y vuelve a correr `python manage.py migrate`. El proyecto ahora usa un modelo de usuario propio (`cuentas.Usuario`) y Django no permite cambiarlo sobre una base ya migrada.

Abre <http://127.0.0.1:8000/> en el navegador. Para detener el servidor, presiona `Ctrl+C`.

## Integrantes Equipo ScorpIO

- Belén — Responsable y Colaboración: http://127.0.0.1:8000/belen/

- Emilaino — Responsable: http://127.0.0.1:8000/tunombre/

## Registro de usuarios (caso de uso 1)

Rutas (app `cuentas`):

| Ruta | Descripción |
|---|---|
| `/cuentas/registro/` | Formulario de registro (Cliente o Empresa) |
| `/cuentas/confirma-tu-correo/` | Aviso de correo enviado y botón «Reenviar correo» |
| `/cuentas/verificar/<token>/` | Enlace que activa la cuenta |
| `/cuentas/reenviar-correo/` | Reenvío del enlace |
| `/cuentas/iniciar-sesion/` | Inicio de sesión (ver más abajo) |
| `/cuentas/inicio/` | Pantalla de inicio (requiere sesión) |

### Probarlo en local

1. `python manage.py runserver`
2. Abre <http://127.0.0.1:8000/cuentas/registro/> y crea una cuenta de Cliente o de Empresa (para Empresa se pide el RFC).
3. En desarrollo los correos **no se envían a Internet**: se imprimen en la terminal donde corre `runserver`. Copia el enlace `http://127.0.0.1:8000/cuentas/verificar/...` y ábrelo en el navegador.
4. Para ver las cuentas: `python manage.py createsuperuser` (pide correo, nombre y contraseña) y entra a <http://127.0.0.1:8000/admin/>.

### Pruebas automatizadas

```bash
python manage.py test cuentas
```

### Configuración por variables de entorno (todas opcionales)

| Variable | Valor por defecto | Uso |
|---|---|---|
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Con `...filebased.EmailBackend` guarda los correos en `correos_desarrollo/` |
| `VERIFICACION_CORREO_HORAS` | `24` | Vigencia del enlace de verificación |
| `DEFAULT_FROM_EMAIL` | `Reserva-Hub <no-reply@reserva-hub.local>` | Remitente |

### Usar un SMTP real más adelante

Definir estas variables antes de iniciar el servidor (ejemplo con Gmail y una contraseña de aplicación):

```bash
export EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
export EMAIL_HOST=smtp.gmail.com
export EMAIL_PORT=587
export EMAIL_USE_TLS=true
export EMAIL_HOST_USER=tu_cuenta@gmail.com
export EMAIL_HOST_PASSWORD=tu_contraseña_de_aplicación
export DEFAULT_FROM_EMAIL="Reserva-Hub <tu_cuenta@gmail.com>"
```

No subas credenciales al repositorio.


## Inicio de sesión (caso de uso 2)

- Se entra con **correo y contraseña** en `/cuentas/iniciar-sesion/`. Solo pueden entrar las cuentas **activas** (con el correo ya verificado).
- Si la cuenta aún está pendiente de verificación, no se crea la sesión y se ofrece «Reenviar correo».
- Tras iniciar sesión se lleva a `/cuentas/inicio/` (o a la página que se pidió, si es del mismo sitio).
- La sesión usa el sistema de sesiones de Django (cookie de sesión; duración por defecto de 2 semanas).
- **Cerrar sesión aún no está implementado** (es otro caso de uso). Mientras tanto, para salir borra la cookie de sesión del navegador o usa una ventana privada.

Probarlo: registra una cuenta, abre el enlace del correo que imprime la terminal y luego inicia sesión en <http://127.0.0.1:8000/cuentas/iniciar-sesion/>.

Pruebas del caso de uso: `python manage.py test cuentas.tests.test_inicio_sesion`

## Publicar espacio (caso de uso 4)

Solo pueden entrar cuentas de tipo Empresa que hayan iniciado sesión. Rutas de la app `espacios`:

| Ruta | Para qué sirve |
|---|---|
| `/espacios/` | Mis espacios |
| `/espacios/publicar/` | Paso 1: información general y fotos |
| `/espacios/publicar/precio-y-horarios/` | Paso 2: precio, modalidad, horarios y sincronizar con Google Calendar |
| `/espacios/publicar/revisar/` | Paso 3: revisar y publicar |
| `/espacios/<id>/publicado/` | Mensaje de espacio publicado |
| `/espacios/google-calendar/` | Vincular el Google Calendar de la empresa |

### Configurar Google Calendar

1. En Google Cloud crear un proyecto, habilitar **Google Calendar API**, crear una **cuenta de servicio** (sin roles) y descargar su clave en JSON.
2. Guardar la clave fuera del repositorio y decirle a Django dónde está:
   ```bash
   export GOOGLE_CALENDAR_CREDENCIALES="$HOME/.config/reserva-hub/google-calendar.json"
   ```
3. En Google Calendar, compartir el calendario con el correo de la cuenta de servicio con el permiso "Ver solo disponibilidad" y copiar el ID del calendario.
4. En la página, entrar a "Vincular Google Calendar" y pegar el ID.

Si no está configurada la variable, al sincronizar sale "No fue posible sincronizar el calendario" (flujo E1).

### Probarlo en local

Como todavía no está "Iniciar sesión", se puede entrar desde el admin con una empresa marcada como staff. Para crear una de prueba:

```bash
python manage.py shell -c "
from cuentas.models import Usuario, Empresa
u, _ = Usuario.objects.get_or_create(correo='empresa.prueba@ejemplo.com', defaults=dict(nombre='Clínica Ejemplo', es_empresa=True, is_active=True, is_staff=True))
u.set_password('Reserva2026-Hub'); u.save()
Empresa.objects.get_or_create(usuario=u, defaults=dict(rfc='CEJ010203AB1'))
"
```

Después entrar a <http://127.0.0.1:8000/admin/login/?next=/espacios/>.

### Pruebas

```bash
python manage.py test espacios
```
