# NexusBack

Backend de **A.T.A.T. ERP**, construido con Django y Django REST Framework
(DRF). Es un monolito modular organizado por dominios.

Actualmente utiliza PostgreSQL alojado en Supabase. Supabase Auth administra la
identidad, las credenciales y las sesiones del módulo `users`.

## Estado actual

- La API usa el prefijo `/api`, sin versionado `/api/v1`.
- El health check está disponible en `GET /api/health/`.
- El módulo `users` está implementado.
- Registro e inicio de sesión son públicos.
- Las operaciones protegidas usan `Authorization: Bearer <access_token>`.
- NexusBack no expone actualmente un endpoint de refresh de sesión.

## Configuración

- Python 3.11 o superior
- `pip` o Docker Compose

```env
DJANGO_SECRET_KEY=your-local-secret-key
```

1. Cree el archivo de configuración local a partir del ejemplo:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Complete en `.env` una clave local de Django, las variables de PostgreSQL y
   las variables de Supabase requeridas. Si PortalWeb se ejecuta en otro origen,
   configure también `CORS_ALLOWED_ORIGINS` con una lista separada por comas. No
   versione ese archivo.

3. Cree y active un entorno virtual, e instale las dependencias:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

4. Con la conexión a PostgreSQL configurada, aplique las migraciones y ejecute
   las verificaciones:

   ```powershell
   python manage.py migrate
   python manage.py check
   ```

5. Inicie el servidor local:

   ```powershell
   python manage.py runserver
   ```

## Docker

Con `.env` configurado, ejecute:

```powershell
docker compose up --build
```

El servicio `nexusback` publica el puerto `8000`. Para ejecutar verificaciones
dentro del contenedor:

```powershell
docker compose exec nexusback python manage.py check
```

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Módulo users](docs/modules/USERS.md)
- [Módulo documents](docs/modules/DOCUMENTS.md)
- [Códigos de error](docs/ERROR_CODES.md)

## Instrucciones para agentes de desarrollo

NexusBack incluye instrucciones versionadas para asistentes de código y agentes internos.

- `AGENTS.md`: convenciones y reglas generales del repositorio.
- `.agents/skills/backend-module/`: guía para crear nuevos módulos respetando la arquitectura existente.
- `.agents/skills/backend-endpoint/`: guía para crear, modificar o revisar endpoints.
- `CLAUDE.md` y `.gemini/settings.json`: integración con herramientas compatibles.

Estas instrucciones buscan mantener consistencia entre contribuciones y evitar cambios de arquitectura o contratos fuera del alcance de cada tarea.
