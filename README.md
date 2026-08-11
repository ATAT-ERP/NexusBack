# NexusBack

Backend principal de **A.T.A.T. ERP**, construido con Django y Django REST
Framework. Este repositorio contiene la base técnica para un monolito modular
orientado a dominios; las funcionalidades del ERP se incorporarán por módulos
en cambios independientes.

## Stack

- Python 3.11+
- Django
- Django REST Framework

## Requisitos

- Python 3.11 o superior
- `pip`

## Preparación local

1. Cree y active un entorno virtual:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instale las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copie `.env.example` como `.env` y reemplace `DJANGO_SECRET_KEY` por una
   clave local segura. El archivo `.env` no se versiona.

4. Aplique las migraciones incluidas por Django (admin, autenticación y
   sesiones):

   ```powershell
   python manage.py migrate
   ```

5. Ejecute las verificaciones y el servidor:

   ```powershell
   python manage.py check
   python manage.py runserver
   ```

El health check técnico está disponible en `GET /api/v1/health/`.

## Estructura

```text
config/  Configuración global y puntos de entrada de Django.
apps/    Contenedor de futuros dominios funcionales.
docs/    Documentación del proyecto.
```

La arquitectura y sus reglas de evolución están documentadas en
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
