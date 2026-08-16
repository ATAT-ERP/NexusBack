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
- `pip` o Docker Compose

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

3. Copie `.env.example` como `.env`, reemplace `DJANGO_SECRET_KEY` por una
   clave local segura y configure todas las variables de PostgreSQL. El archivo
   `.env` no se versiona; NexusBack no admite SQLite como fallback.

4. Cuando la conexión PostgreSQL esté validada, aplique las migraciones de los
   dominios del ERP:

   ```powershell
   python manage.py migrate
   ```

5. Ejecute las verificaciones y el servidor:

   ```powershell
   python manage.py check
   python manage.py runserver
   ```

Para desarrollo con Docker, configure `.env` y ejecute:

```powershell
docker compose up --build
```

Para logs o verificaciones dentro del contenedor, el servicio es `nexusback`:

```powershell
docker compose logs -f nexusback
docker compose exec nexusback python manage.py check
```

El health check técnico está disponible en `GET /api/health/`.

## Estructura

```text
config/  Configuración global y puntos de entrada de Django.
apps/    Contenedor de futuros dominios funcionales.
docs/    Documentación del proyecto.
```

La arquitectura y sus reglas de evolución están documentadas en
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
