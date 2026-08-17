# Módulo `users`

## Finalidad

`users` representa el perfil local de los usuarios del ERP. La autenticación
pertenece a Supabase Auth y el perfil de aplicación se almacena en
`public.users`.

El identificador es un UUID pensado para coincidir con el UUID de Supabase
Auth. Actualmente no existe una clave foránea física entre `public.users` y
`auth.users`.

## Modelo actual

La tabla física es `public.users` y contiene los siguientes campos:

| Campo | Descripción |
| --- | --- |
| `id` | UUID y clave primaria del perfil. |
| `first_name` | Nombre; puede comenzar vacío. |
| `last_name` | Apellido; puede comenzar vacío. |
| `avatar_path` | Ruta del avatar opcional. |
| `is_active` | Estado local del usuario. |
| `is_system_admin` | Administración global del sistema, no un rol por empresa. |

## Estructura actual

```text
apps/users/
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── migrations/
├── apps.py
└── models.py
```

## Flujo actual

```text
/api/users/
      ↓
DRF Router
      ↓
UserViewSet
      ↓
UserSerializer
      ↓
User / Django ORM
      ↓
public.users
```

Las operaciones CRUD estándar se resuelven principalmente mediante mixins de
DRF y el ORM de Django, evitando wrappers innecesarios en el modelo.

## Endpoints actuales

```text
GET    /api/users/
POST   /api/users/

GET    /api/users/<uuid>/
PUT    /api/users/<uuid>/
PATCH  /api/users/<uuid>/
```

`DELETE` no está implementado actualmente.

## Errores

Los códigos aplicables al módulo incluyen `NEX-USR-003` para datos inválidos y
`NEX-USR-004` para un usuario inexistente. La fuente de verdad del catálogo es
[docs/ERROR_CODES.md](../ERROR_CODES.md).

## Estado de autenticación

- El CRUD básico de `users` está implementado.
- Supabase PostgreSQL está conectado y la migración inicial está aplicada.
- Supabase Auth todavía no está integrado en NexusBack.
- JWT todavía no está implementado.
- El endpoint de registro todavía no existe.
