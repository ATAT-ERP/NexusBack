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

Cree una instancia de Blueprint en Render usando `render.yaml` y seleccione la
rama a desplegar. Define un Web Service Python 3.11 con Gunicorn y health check
en `/api/health/`. El build sólo instala `requirements.txt`; no aplica migraciones.
El plan gratuito suspende el servicio por inactividad y no incluye Shell.
Docker Compose conserva su uso para desarrollo y pruebas.

Configure las variables solicitadas por el blueprint según `.env.example`:

- `DJANGO_DEBUG=False` y `DJANGO_TRUST_PROXY_HEADERS=True` (incluidas).
- `DJANGO_SECRET_KEY` privada, generada por el blueprint.
- `DJANGO_ALLOWED_HOSTS`: hosts públicos explícitos, sin esquema ni comodines.
- `CORS_ALLOWED_ORIGINS`: orígenes HTTPS de PortalWeb, separados por comas.
  `CSRF_TRUSTED_ORIGINS` sólo si hay solicitudes que requieran CSRF.
- `POSTGRES_DB`, `POSTGRES_USER`, `DB_PASSWORD`, `POSTGRES_HOST` y `POSTGRES_PORT`:
  datos de la base existente de Supabase. Para Session pooler, copie el host y
  usuario correspondientes y use el puerto `5432`. Se mantiene `sslmode=require`.
- `SUPABASE_URL`, `SUPABASE_KEY` y `SUPABASE_SECRET_KEY`: integración existente de
  Auth y Storage; la clave secreta permanece exclusivamente en el servidor.

Render termina HTTPS y Django mantiene redirección HTTPS y cookies seguras.
HSTS comienza con una hora en producción; puede ajustar `DJANGO_SECURE_HSTS_SECONDS`
tras verificar HTTPS. El valor `0` deja de emitir el encabezado, pero no borra las
políticas ya almacenadas en los navegadores. No se habilitan subdominios ni preload.
No hay estáticos propios, Admin ni Browsable API; no se necesita `collectstatic`.
Los documentos permanecen en Supabase Storage.

Antes de publicar una versión que cambie el esquema, desde un entorno autorizado
con las dependencias y variables de producción de esa misma versión:

```sh
python manage.py showmigrations --plan
python manage.py migrate --plan
```

Revise las migraciones pendientes, su SQL cuando corresponda y la compatibilidad
con la versión en servicio. Después de disponer de un respaldo de Supabase,
ejecútelas manualmente y coordine la publicación de la versión:

```sh
python manage.py migrate
```

No configure migraciones en el build ni en el arranque. Antes de desplegar, ejecute
`python manage.py check` y `python manage.py check --deploy`. Este último advertirá
sobre `SECURE_HSTS_INCLUDE_SUBDOMAINS` y `SECURE_HSTS_PRELOAD`, deshabilitados
deliberadamente; revise cualquier otra advertencia.

Verifique la URL pública con `Invoke-RestMethod https://<servicio>.onrender.com/api/health/`:
debe devolver HTTP 200 con `{"status": "ok"}`. El health check verifica el proceso;
compruebe también los flujos de la API que usan PostgreSQL y Storage.

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
