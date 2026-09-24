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

Abre <http://127.0.0.1:8000/> en el navegador. Para detener el servidor, presiona `Ctrl+C`.

## Integrantes Equipo ScorpIO

- Belén — Responsable y Colaboración: http://127.0.0.1:8000/belen/