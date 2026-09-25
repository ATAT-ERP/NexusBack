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

Cree el archivo `.env` a partir del ejemplo y complete las variables requeridas.

```powershell
Copy-Item .env.example .env
```

## Docker

```powershell
docker compose up --build
```

La API queda disponible en `http://localhost:8000`.

## Ejecución local

Cree el entorno virtual:

```powershell
python -m venv .venv
```

Active el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale las dependencias:

```powershell
python -m pip install -r requirements.txt
```

Aplique las migraciones:

```powershell
python manage.py migrate
```

Inicie el servidor:

```powershell
python manage.py runserver
```

## Documentación

* [Arquitectura](docs/ARCHITECTURE.md)
* [Módulo users](docs/modules/USERS.md)
* [Módulo documents](docs/modules/DOCUMENTS.md)
* [Códigos de error](docs/ERROR_CODES.md)

Las convenciones del repositorio y las instrucciones para agentes de desarrollo se encuentran en [`AGENTS.md`](AGENTS.md).
