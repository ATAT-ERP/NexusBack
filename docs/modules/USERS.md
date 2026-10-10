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
identidad + UUID
      ↓
public.users (perfil local mínimo)
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
sesión + identidad verificada
      ↓
sincronización del perfil local por UUID
      ↓
validación de perfil activo
      ↓
tokens al cliente
```

## Endpoints actuales

```text
GET    /api/users/
GET    /api/users/search/?q=valor
GET    /api/users/me/
PATCH  /api/users/me/
POST   /api/users/register/
POST   /api/users/login/
POST   /api/users/logout/
POST   /api/users/password/change/

GET    /api/users/<uuid>/
PUT    /api/users/<uuid>/
PATCH  /api/users/<uuid>/
POST   /api/users/<uuid>/system-admin/
POST   /api/users/<uuid>/activate/
POST   /api/users/<uuid>/deactivate/
```

`DELETE` no está implementado actualmente.

La creación directa de perfiles mediante `POST /api/users/` no está disponible.
El registro normal usa `POST /api/users/register/`; las identidades creadas
directamente en Supabase Auth se sincronizan tras autenticar un token o iniciar
sesión. El perfil propio se consulta con `GET /api/users/me/` y se actualiza con
`PATCH /api/users/me/`;
la identidad se obtiene del Bearer y no de un UUID enviado por el cliente. Sólo
se pueden modificar `first_name` y `last_name`. Las escrituras rechazan `id`,
`email`, `avatar_path`, `is_active`, `is_system_admin` y cualquier otro campo.
Los campos personales omitidos en un PATCH conservan su valor. Los endpoints
por UUID existentes se mantienen para compatibilidad y administración; un
usuario normal sólo accede a su propio UUID. Un futuro cambio de email deberá
actualizar primero Supabase Auth y luego `public.users`.

La búsqueda consulta únicamente `public.users` por nombre, apellido o email,
sin distinguir mayúsculas y minúsculas.

### Contrato del perfil propio

`GET /api/users/me/` responde con `id`, `email`, `first_name`, `last_name`,
`avatar_path`, `is_active` e `is_system_admin`. `PATCH /api/users/me/` acepta,
por ejemplo, `{"first_name":"Ana","last_name":"Pérez"}` y devuelve el
perfil actualizado con el mismo serializer. Los campos de perfil que no se
incluyen en el PATCH conservan sus valores.

Un dato inválido o un campo protegido devuelve `400 Bad Request` con el formato
`{"code":"NEX-USR-003","message":"Los datos enviados no son válidos.","errors":{...}}`.
La falta de Bearer devuelve `401`; la falta de permisos o un perfil inactivo
devuelve `403`.

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
`NEX-USR-013` representa un fallo de Supabase al cerrar una sesión y
`NEX-USR-014` un fallo de Supabase al actualizar la contraseña. La fuente de
verdad del catálogo es [docs/ERROR_CODES.md](../ERROR_CODES.md).

## Estado de autenticación

- `POST /api/users/register/` y `POST /api/users/login/` son públicos.
- `POST /api/users/logout/` requiere Bearer y cierra con scope local la sesión
  de Supabase representada por ese token; responde `204 No Content`.
- `POST /api/users/password/change/` requiere Bearer y recibe
  `current_password`, `new_password` y `confirm_password`. Sólo actualiza la
  contraseña de la identidad autenticada en Supabase Auth; no modifica
  `public.users` y responde `204 No Content`.
- El access JWT emitido puede seguir siendo válido hasta su expiración después
  del logout. El cliente debe descartar sus access y refresh tokens tras el 204.
- Los demás endpoints de `users` requieren `Authorization: Bearer <access_token>`.
- NexusBack valida el Bearer ante Supabase Auth y crea un perfil local mínimo
  cuando la identidad verificada todavía no tiene uno. La sincronización usa el
  UUID y email devueltos por Supabase, no metadata del cliente, y no concede
  privilegios administrativos. Si el email ya pertenece a otro UUID local, la
  identidad se rechaza sin vincular perfiles.
- El login sincroniza perfiles ausentes a partir de la identidad devuelta por
  Supabase Auth. El registro crea el perfil desde la respuesta de Supabase.
  Los perfiles nuevos usan los defaults del modelo: activos y sin privilegios
  de administrador.
- Si Supabase crea una cuenta pero falla la creación del perfil local, el
  registro responde con un error interno; la cuenta remota no se revierte.
- Un perfil con `is_active = False` no puede iniciar sesión ni operar con un
  Bearer válido. Un usuario inactivo no puede reactivarse a sí mismo.
- Un usuario normal sólo puede consultar y editar su propio perfil.
- Un administrador global puede listar, buscar, consultar y editar cualquier
  perfil. El listado y la búsqueda son administrativos y no están disponibles
  para incorporar colaboradores; Company mantiene esa operación por correo.
  También puede activar, desactivar y cambiar `is_system_admin` de otros
  usuarios mediante las acciones administrativas explícitas.
- Un administrador no puede desactivarse ni quitarse su propio privilegio.
- Supabase PostgreSQL está conectado y la migración inicial está aplicada.
- El registro email/password mediante Supabase Auth está implementado.
- El login email/password mediante Supabase Auth está implementado.
- El cambio autogestionado de contraseña mediante Supabase Auth está implementado.
- La confirmación de email está desactivada en la configuración actual del proyecto.
- Refresh todavía no está implementado.
- Google Auth todavía no está implementado.

Si Supabase Auth crea la cuenta pero falla la creación de `public.users`, el
backend responde el error de perfil local. No se revierte la cuenta remota:
la operación `sign_up` usa una clave publishable o anon y no puede eliminarla
de forma segura sin añadir privilegios administrativos.
