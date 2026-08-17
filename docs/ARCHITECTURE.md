# Arquitectura de NexusBack

## Objetivo

NexusBack es el backend de A.T.A.T. ERP. Está construido con Django y Django
REST Framework (DRF) como un monolito modular orientado a dominios: una única
aplicación desplegable organizada en módulos funcionales independientes.

## Estructura general

```text
NexusBack/
├── config/     # Configuración global, ASGI/WSGI y rutas agregadoras
├── apps/       # Módulos funcionales del backend
├── docs/       # Documentación técnica, arquitectónica y por módulo
├── manage.py
└── requirements.txt
```

`config/` contiene configuración global y no lógica de negocio. `apps/`
contiene los dominios funcionales existentes y los que se incorporen en el
futuro. `shared/` sólo se creará para elementos realmente transversales y
reutilizados por varios módulos; no es una capa creada por defecto.

## Módulos y responsabilidades

Cada dominio se implementa como una Django App dentro de `apps/<domain>/`.
Un módulo puede incorporar `models`, `migrations`, `api`, `services`,
`selectors`, `permissions` o pruebas según una necesidad concreta. Ninguna de
esas capas es obligatoria por convención.

- **Models y ORM:** representan y persisten datos mediante Django ORM.
- **API:** agrupa serializers, views, viewsets y rutas HTTP del dominio.
- **Services y selectors:** se crean sólo cuando una regla de negocio o una
  consulta justifica separar esa responsabilidad.

DRF y el ORM deben aprovecharse para operaciones estándar cuando ofrecen una
solución clara. Por ejemplo, los mixins de DRF pueden resolver CRUDs
convencionales sin duplicar acciones en un ViewSet. Los modelos sólo deben
tener métodos propios cuando aporten comportamiento de dominio; no deben ser
wrappers de llamadas simples como `User.objects.get(...)`,
`User.objects.create(...)` o `User.objects.all()`.

## Flujo general de una API

```text
HTTP
  ↓
URL / Router
  ↓
View / ViewSet
  ↓
Serializer
  ↓
Model / Django ORM
  ↓
PostgreSQL
```

- **URL / Router:** expone los endpoints.
- **View / ViewSet:** gestiona el flujo HTTP y construye las respuestas.
- **Serializer:** transforma datos y aplica validación defensiva.
- **Model / ORM:** representa y persiste los datos.
- **Services / Selectors:** separan lógica o consultas sólo si su complejidad lo
  requiere.

## API y rutas

La API se organiza bajo `/api/...`, sin versionado `/v1`. `config/urls.py`
agrega las rutas globales y cada módulo mantiene sus propias rutas. Los routers
de DRF son la opción preferida para recursos convencionales; las rutas
explícitas se reservan para operaciones especiales.

## Datos, migraciones y autenticación

PostgreSQL alojado en Supabase es la base de datos del proyecto. Cada módulo es
responsable de sus propias migraciones Django y las versiona junto con la app.

Supabase Auth se utiliza para las operaciones de autenticación implementadas
por los módulos que lo requieren, incluidos el registro y el inicio de sesión.
La validación de JWT/Bearer para proteger endpoints todavía está pendiente;
NexusBack no almacena contraseñas. Los detalles de `users` se documentan en
`docs/modules/USERS.md`.

## Documentación por módulo

Los detalles de implementación y estado de cada dominio se documentan en
`docs/modules/`. La documentación actual del perfil local de usuarios está en
[docs/modules/USERS.md](modules/USERS.md).

## Principios de evolución

- Mantener la lógica dentro de su dominio propietario.
- Evitar dependencias circulares y abstracciones prematuras.
- Incorporar capas y código compartido sólo cuando aporten una responsabilidad
  real y reutilizable.
- Mantener la documentación arquitectónica alineada con los cambios generales
  del backend.
