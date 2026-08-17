# Módulo `users`

## Finalidad

`users` representa el perfil local de los usuarios del ERP. La autenticación
pertenece a Supabase Auth y el perfil de aplicación se almacena en
`public.users`.

El identificador es un UUID pensado para coincidir con el UUID de Supabase
Auth. Actualmente no existe una clave foránea física entre `public.users` y
`auth.users`.

Supabase Auth es la fuente de verdad de identidad y autenticación.
`public.users.email` es una copia operativa para consultas del ERP. Los nuevos
registros guardan el mismo email usado en Supabase Auth; los usuarios históricos
pueden conservar temporalmente `email = null`.

## Modelo actual

La tabla física es `public.users` y contiene los siguientes campos:

| Campo | Descripción |
| --- | --- |
| `id` | UUID y clave primaria del perfil. |
| `email` | Copia operativa del email; puede ser `null` en usuarios históricos. |
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
GET    /api/users/search/?q=valor
POST   /api/users/register/
POST   /api/users/login/
POST   /api/users/logout/

GET    /api/users/<uuid>/
PUT    /api/users/<uuid>/
PATCH  /api/users/<uuid>/
POST   /api/users/<uuid>/system-admin/
POST   /api/users/<uuid>/activate/
POST   /api/users/<uuid>/deactivate/
```

`DELETE` no está implementado actualmente.

La creación directa de perfiles mediante `POST /api/users/` no está disponible:
todo usuario nuevo debe pasar por `POST /api/users/register/`. En el CRUD
normal, `id`, `email`, `is_active` e `is_system_admin` son de solo lectura. Un
futuro cambio de email deberá actualizar primero Supabase Auth y luego
`public.users`.

La búsqueda consulta únicamente `public.users` por nombre, apellido o email,
sin distinguir mayúsculas y minúsculas.

## Operaciones administrativas

Estas rutas requieren un Bearer válido cuyo perfil local tenga
`is_system_admin = True`:

- `POST /api/users/<uuid>/system-admin/` recibe
  `{"is_system_admin": true|false}` y cambia ese privilegio en otro usuario.
- `POST /api/users/<uuid>/activate/` activa el perfil local objetivo.
- `POST /api/users/<uuid>/deactivate/` desactiva el perfil local objetivo.

Un administrador no puede desactivarse ni quitarse su propio privilegio. Estas
operaciones no eliminan perfiles locales ni usuarios de Supabase Auth.

## Errores

Los códigos aplicables al módulo incluyen `NEX-USR-003` para datos inválidos,
`NEX-USR-004` para un usuario inexistente, `NEX-USR-005` para una cuenta no
creada por Supabase Auth, `NEX-USR-006` para un perfil local no creado,
`NEX-USR-007` para rate limit, `NEX-USR-008` para credenciales inválidas y
`NEX-USR-009` para un fallo de login. `NEX-USR-010` representa un Bearer
ausente, mal formado o inválido, `NEX-USR-011` una falta de permisos y
`NEX-USR-012` un fallo interno al validar el perfil local autenticado.
`NEX-USR-013` representa un fallo de Supabase al cerrar una sesión. La fuente de
verdad del catálogo es [docs/ERROR_CODES.md](../ERROR_CODES.md).

## Estado de autenticación

- `POST /api/users/register/` y `POST /api/users/login/` son públicos.
- `POST /api/users/logout/` requiere Bearer y cierra con scope local la sesión
  de Supabase representada por ese token; responde `204 No Content`.
- El access JWT emitido puede seguir siendo válido hasta su expiración después
  del logout. El cliente debe descartar sus access y refresh tokens tras el 204.
- Los demás endpoints de `users` requieren `Authorization: Bearer <access_token>`.
- NexusBack valida el Bearer ante Supabase Auth, busca el UUID en `public.users`
  y rechaza perfiles inexistentes o inactivos.
- Un usuario normal sólo puede consultar y editar su propio perfil.
- Un administrador global puede listar, buscar, consultar y editar cualquier
  perfil. También puede activar, desactivar y cambiar `is_system_admin` de otros
  usuarios mediante las acciones administrativas explícitas.
- Un administrador no puede desactivarse ni quitarse su propio privilegio.
- Supabase PostgreSQL está conectado y la migración inicial está aplicada.
- El registro email/password mediante Supabase Auth está implementado.
- El login email/password mediante Supabase Auth está implementado.
- La confirmación de email está desactivada en la configuración actual del proyecto.
- Refresh todavía no está implementado.
- Logout todavía no está implementado.
- Google Auth todavía no está implementado.

Si Supabase Auth crea la cuenta pero falla la creación de `public.users`, el
backend responde el error de perfil local. No se revierte la cuenta remota:
la operación `sign_up` usa una clave publishable o anon y no puede eliminarla
de forma segura sin añadir privilegios administrativos.
