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
| `/cuentas/iniciar-sesion/` | **Provisional**: se reemplaza al implementar «Iniciar sesión» |

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
