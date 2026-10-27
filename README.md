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

En Render, configure las variables del servidor en el entorno del servicio: use
`DJANGO_DEBUG=False`, una `DJANGO_SECRET_KEY` privada, los hosts y orígenes HTTPS
reales, y los datos de PostgreSQL/Supabase. `DJANGO_TRUST_PROXY_HEADERS=True` sólo
se activa detrás del proxy HTTPS de Render. No implemente ni ejecute el despliegue
con la configuración local de Docker Compose.

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
