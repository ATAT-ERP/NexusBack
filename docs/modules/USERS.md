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
├── authentication.py
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

El registro sigue este flujo:

```text
Portal / Mobile
      ↓
NexusBack
      ↓
Supabase Auth
      ↓
UUID
      ↓
public.users
```

El login sigue este flujo:

```text
Portal / Mobile
      ↓
POST /api/users/login/
      ↓
NexusBack
      ↓
Supabase Auth
      ↓
sesión + UUID
      ↓
public.users
      ↓
validación de perfil activo
      ↓
tokens al cliente
```

## Endpoints actuales

```text
GET    /api/users/
POST   /api/users/
POST   /api/users/register/
POST   /api/users/login/

GET    /api/users/<uuid>/
PUT    /api/users/<uuid>/
PATCH  /api/users/<uuid>/
```

`DELETE` no está implementado actualmente.

## Errores

Los códigos aplicables al módulo incluyen `NEX-USR-003` para datos inválidos,
`NEX-USR-004` para un usuario inexistente, `NEX-USR-005` para una cuenta no
creada por Supabase Auth, `NEX-USR-006` para un perfil local no creado,
`NEX-USR-007` para rate limit, `NEX-USR-008` para credenciales inválidas y
`NEX-USR-009` para un fallo de login. La fuente de verdad del catálogo es
[docs/ERROR_CODES.md](../ERROR_CODES.md).

## Estado de autenticación

- El CRUD básico de `users` está implementado.
- Supabase PostgreSQL está conectado y la migración inicial está aplicada.
- El registro email/password mediante Supabase Auth está implementado.
- El login email/password mediante Supabase Auth está implementado.
- La confirmación de email está desactivada en la configuración actual del proyecto.
- Los JWT todavía no se validan en los endpoints de NexusBack.
- Refresh todavía no está implementado.
- Logout todavía no está implementado.
- Google Auth todavía no está implementado.

Si Supabase Auth crea la cuenta pero falla la creación de `public.users`, el
backend responde el error de perfil local. No se revierte la cuenta remota:
la operación `sign_up` usa una clave publishable o anon y no puede eliminarla
de forma segura sin añadir privilegios administrativos.
