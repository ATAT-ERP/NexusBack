<h1 align="center">NexusBack</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/DRF-A30000?style=for-the-badge&logo=django&logoColor=white" alt="Django REST Framework">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

Backend de **A.T.A.T. ERP**, construido con Django y Django REST Framework.
Está organizado como un monolito modular por dominios y utiliza PostgreSQL en Supabase junto con Supabase Auth para autenticación.

## Configuración

Necesita Docker Desktop con Docker Compose y las credenciales del entorno de
desarrollo de PostgreSQL/Supabase. Desde la raíz del repositorio, cree `.env`:

```powershell
Copy-Item .env.example .env
```

Complete en `.env` la clave de Django, los datos de PostgreSQL y las claves del proyecto
Supabase. `SUPABASE_KEY` es la clave publicable/anon; `SUPABASE_SECRET_KEY` es
exclusiva del servidor. No agregue credenciales al repositorio. `.env` está excluido
de Git y Docker Compose entrega sus variables al contenedor.

Para iniciar el servidor:

```powershell
docker compose up --build
```

La API queda disponible en `http://localhost:8000/api/` y la verificación de estado en
`http://localhost:8000/api/health/`. Para detener y retirar los contenedores:

```powershell
docker compose down
```

En desarrollo, `DJANGO_ALLOWED_HOSTS` configura los hosts HTTP y
`CORS_ALLOWED_ORIGINS` configura los sitios web autorizados; cada variable contiene
una lista separada por comas. El `.env.example` incluye valores locales. PortalWeb
usa `http://localhost:5173`; el emulador Android estándar accede por
`http://10.0.2.2:8000/api/`.

Para usar un teléfono físico, configure Django para escuchar dentro del contenedor
(Compose ya publica el puerto `8000`) y agregue la IP de la red local de la computadora a
`DJANGO_ALLOWED_HOSTS`. En el teléfono, use `http://<IP-RED-LOCAL-DE-LA-COMPUTADORA>:8000/api/`.
El puerto debe estar permitido en el firewall. Si una página web del teléfono llama
a la API, agregue además el origen de esa página a `CORS_ALLOWED_ORIGINS`. Una aplicación
móvil nativa no usa CORS.

Si cambia una lista en `.env`, vuelva a ejecutar `docker compose up` para recrear el
servicio con esas variables. Los valores explícitos en `.env` reemplazan los valores
predeterminados y no se combinan con ellos.

### Producción (Render y Supabase)

El repositorio está preparado para ejecutarse como **Web Service** de Render con
Gunicorn y la base PostgreSQL de Supabase. Render usa su runtime Python; el
`Dockerfile` y `compose.yaml` quedan para desarrollo y pruebas.

#### Crear el servicio

1. En Render, cree un **Web Service** y vincule el repositorio de GitHub.
2. Seleccione la rama de producción y el runtime **Python**. El archivo
   `.python-version` fija Python 3.11.
3. Defina los comandos:
   - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`
   - **Start Command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
   - **Health Check Path:** `/api/health/`
4. También puede aplicar el blueprint incluido en `render.yaml` desde
   **Blueprints > New Blueprint Instance**. El blueprint usa el plan gratuito y
   solicita las variables marcadas como secretas.

En el plan gratuito Render suspende el servicio por inactividad: el primer
request después de una pausa puede tardar en responder. El plan gratuito no
ofrece Shell ni pre-deploy; por eso el build aplica las migraciones antes de
publicar la nueva versión.

#### Variables de entorno

Configure en Render, sin agregar valores reales al repositorio:

| Variable | Valor |
| --- | --- |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Clave aleatoria segura (mínimo 50 caracteres; no usar `django-insecure-`). En el blueprint se genera automáticamente. |
| `DJANGO_ALLOWED_HOSTS` | Hosts públicos separados por comas, por ejemplo `nexusback.onrender.com,api.example.com`. Sin comodines. |
| `CORS_ALLOWED_ORIGINS` | Orígenes HTTPS de PortalWeb, por ejemplo `https://portal.example.com`. Sin comodines. |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS que necesiten CSRF, normalmente el mismo origen de PortalWeb. Puede quedar vacío. |
| `DJANGO_TRUST_PROXY_HEADERS` | `True` (Render termina HTTPS y envía `X-Forwarded-Proto`). |
| `POSTGRES_DB` | Nombre de la base de Supabase. |
| `POSTGRES_USER` | Usuario de la base de Supabase. |
| `DB_PASSWORD` | Contraseña de la base de Supabase. |
| `POSTGRES_HOST` | Host de conexión de Supabase (se recomienda la conexión **Session pooler**). |
| `POSTGRES_PORT` | Puerto de conexión de Supabase (`5432` para la conexión directa o Session pooler). |
| `SUPABASE_URL` | URL del proyecto Supabase. |
| `SUPABASE_KEY` | Clave publicable/anon de Supabase. |
| `SUPABASE_SECRET_KEY` | Clave secreta de servidor para Supabase Storage. No compartir con PortalWeb ni Orbit. |

Opcionalmente ajuste `DOCUMENT_MAX_SIZE_MB`, `DOCUMENT_COMPANY_LIMIT_MB` y
`DOCUMENT_STORAGE_SAFE_LIMIT_MB`. La conexión usa `sslmode=require`, requerido
por Supabase; no se configura una segunda base en Render.

#### Migraciones y datos

El comando de build ejecuta `python manage.py migrate --noinput`, por lo que
aplica únicamente migraciones pendientes antes de iniciar la nueva versión y
cancela el deploy si alguna falla. Antes de desplegar un cambio de esquema:

1. Revise las migraciones incluidas en el repositorio.
2. Confirme que no haya operaciones destructivas ni datos de prueba.
3. Realice un respaldo de Supabase.
4. Despliegue y verifique `/api/health/`.

Si el servicio pasa a un plan pago, puede mover `python manage.py migrate
--noinput` del build al **Pre-Deploy Command** de Render para separar la
migración de la construcción. No ejecute migraciones manuales contra producción
sin revisar antes el SQL y contar con respaldo.

#### Archivos estáticos, HTTPS y errores

- `collectstatic` genera `staticfiles/` durante el build y WhiteNoise los sirve
  desde la instancia. Los archivos subidos por usuarios no se guardan en Render:
  la aplicación mantiene Supabase Storage y la clave `SUPABASE_SECRET_KEY`.
- Render termina TLS. Con `DJANGO_TRUST_PROXY_HEADERS=True`, Django confía en
  `X-Forwarded-Proto`, redirige a HTTPS y usa cookies seguras. En producción se
  envía HSTS por un año; `DJANGO_SECURE_HSTS_SECONDS=0` lo desactiva si fuera
  necesario.
- Con `DJANGO_DEBUG=False`, Django no muestra trazas ni detalles internos en las
  respuestas de error.

#### Verificar el servicio

Con la URL pública de Render:

```powershell
Invoke-RestMethod https://<servicio>.onrender.com/api/health/
```

Debe responder `200` con:

```json
{"status": "ok"}
```

Las rutas de la API siguen bajo `/api/`. Para comprobar la configuración de
producción, cargue las variables en el entorno y ejecute:

```powershell
python manage.py check
python manage.py check --deploy
```

Ambos comandos deben finalizar sin errores ni advertencias de seguridad
pendientes. No ejecute `runserver` en producción; Gunicorn es el servidor del
servicio.

## Pruebas

Con Docker Desktop iniciado, use `compose.test.yaml` desde la raíz del repositorio. Reutiliza el `Dockerfile`, instala `requirements.txt` en la imagen y espera a que el PostgreSQL de pruebas esté listo. Este servicio no publica su puerto; la configuración de Django ignora `.env`, usa valores ficticios para Supabase y se conecta sólo a `test-db`.

```powershell
docker compose -f compose.test.yaml run --build --rm tests python manage.py test apps.company.tests.test_create --settings=config.test_settings --noinput
docker compose -f compose.test.yaml run --build --rm tests python manage.py test apps.company --settings=config.test_settings --noinput
docker compose -f compose.test.yaml run --build --rm tests
docker compose -f compose.test.yaml down -v
```

Puede agregar `.CompanyCreateTests` o `.CompanyCreateTests.test_create_individual_without_tax_info` a la etiqueta del primer comando para seleccionar una clase o método. Para pedirle a Codex que elija las pruebas relacionadas con un cambio, solicite `Usá $nexusback-tests para probar estos cambios`.

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Módulo users](docs/modules/USERS.md)
- [Módulo cloud](docs/modules/CLOUD.md)
- [Módulo accounting](docs/modules/ACCOUNTING.md)
- [Códigos de error](docs/ERROR_CODES.md)

Las convenciones del repositorio y las instrucciones para agentes de desarrollo se encuentran en [`AGENTS.md`](AGENTS.md).
