# NexusBack

Backend principal de **A.T.A.T. ERP**, desarrollado con Django y Django REST Framework.

El proyecto utiliza una arquitectura de monolito modular orientada a dominios.

## Stack

* Python 3.11+
* Django
* Django REST Framework
* Docker

## Configuración

Copie `.env.example` como `.env` y defina una clave local para:

```env
DJANGO_SECRET_KEY=your-local-secret-key
```

El archivo `.env` contiene la configuración local y no se versiona.

## Desarrollo con Docker

### Primer arranque

```bash
docker compose up --build
```

### Arranques posteriores

```bash
docker compose up
```

Para ejecutarlo en segundo plano:

```bash
docker compose up -d
```

Para detenerlo:

```bash
docker compose down
```

Para consultar los logs:

```bash
docker compose logs -f nexusback
```

Para verificar la configuración de Django:

```bash
docker compose exec nexusback python manage.py check
```

El backend queda disponible en:

```text
http://localhost:8000
```

Health check:

```text
GET http://localhost:8000/api/v1/health/
```

Los cambios realizados en el código se reflejan automáticamente mediante el autoreload de Django. Solo es necesario reconstruir la imagen cuando cambien las dependencias o el `Dockerfile`.

## Desarrollo sin Docker

Como alternativa, puede ejecutarse localmente con Python 3.11 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py check
python manage.py runserver
```

## Estructura

```text
config/  Configuración global de Django.
apps/    Dominios funcionales del sistema.
docs/    Documentación del proyecto.
```

Las decisiones y reglas de arquitectura se encuentran en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
