# Módulo `company`

## Finalidad

`company` representa el espacio de trabajo de un cliente dentro de A.T.A.T. y
de la cartera que administra un contador. Puede corresponder a una persona con
actividad individual o a una PyME/organización. La compañía conserva sus datos
administrativos y de contacto; no requiere validación fiscal externa para
existir.

El identificador es un UUID generado localmente por la aplicación en el momento
de la creación; a diferencia de `users`, no proviene de un sistema externo.

El label de la aplicación Django es `companies` (plural), mientras que el
paquete Python es `apps.company`. La tabla física es `public.companies`.

## Modelo actual

La tabla física es `public.companies` y contiene los siguientes campos:

| Campo | Descripción |
| --- | --- |
| `id` | UUID generado por defecto y clave primaria. |
| `type` | Tipo de actividad: `individual` (por defecto) u `organization`. |
| `name` | Nombre de la compañía; obligatorio. |
| `legal_name` | Razón social opcional. |
| `tax_id` | Identificador fiscal (CUIT) opcional; se guarda normalizado y único. |
| `email` | Correo de contacto opcional. |
| `phone` | Teléfono opcional. |
| `address_street` | Calle de la dirección opcional. |
| `address_number` | Número de la dirección opcional. |
| `address_city` | Ciudad opcional. |
| `address_postal_code` | Código postal opcional. |
| `address_province` | Provincia opcional. |
| `address_country` | País opcional. |
| `is_active` | Estado de la compañía; `True` por defecto. |
| `created_at` | Fecha de creación. |
| `updated_at` | Última fecha de modificación. |

## Estructura actual

```text
apps/company/
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── models/
│   ├── company.py
│   ├── member.py
│   └── role.py
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_company_unique_company_tax_id.py
│   ├── 0003_companyrole_companymember.py
│   └── 0004_initial_company_roles.py
├── tests/
│   ├── test_create.py
│   ├── test_list.py
│   ├── test_membership.py
│   ├── test_permissions.py
│   ├── test_search.py
│   └── test_update.py
├── apps.py
└── models.py
```

## Endpoints actuales

```text
GET   /api/companies/?is_active=true|false|all
POST  /api/companies/
GET   /api/companies/search/?q=...
GET   /api/companies/{id}/
PUT   /api/companies/{id}/
PATCH /api/companies/{id}/
DELETE /api/companies/{id}/
GET   /api/companies/{id}/members/
POST  /api/companies/{id}/members/
PATCH /api/companies/{id}/members/{user_id}/
DELETE /api/companies/{id}/members/{user_id}/
```

Todos los endpoints requieren autenticación Bearer mediante
`SupabaseBearerAuthentication`. El usuario sólo puede consultar Companies donde
tenga una membresía `CompanyMember`. El detalle de una Company ajena responde
`404` para no revelar si existe.

El listado y la búsqueda se limitan a las Companies del usuario. Ambos aceptan
los mismos filtros:

| Parámetro | Valores | Comportamiento |
| --- | --- | --- |
| `is_active` | `true`, `false`, `all` | Por defecto `true`; `false` devuelve inactivas y `all` ambas. |
| `type` | `individual`, `organization` | Filtra por tipo; sin parámetro incluye ambos. |

La búsqueda también acepta `q` y busca por nombre, razón social o CUIT. Una
búsqueda sin `q` o sin coincidencias devuelve `200` con `[]`. El campo público
de solo lectura `my_role` indica el rol del usuario autenticado en cada Company
(`owner` o `member`), según su membresía. Está presente en listado, búsqueda,
detalle y alta.

Los parámetros `is_active` y `type` inválidos responden `400` con el contrato
de validación `NEX-COM-001`.

### Alta (POST /api/companies/)

Registra una nueva compañía. Responde `201 Created` con el cuerpo de la compañía
creada (incluye su `id` y `my_role: "owner"`) y crea una membresía `owner` para
el usuario que la registró. Responde `400 Bad Request` cuando falla la
validación.

#### Path

```text
POST /api/companies/
```

#### Request (application/json)

| Campo | Tipo | Obligatorio | Contracto |
| --- | --- | --- | --- |
| `type` | `string` | No (defecto `individual`) | `individual` \| `organization` |
| `name` | `string` | **Sí** | Nombre de la compañía. |
| `legal_name` | `string` or `null` | No | Razón social. Vacío se persiste como `null`. |
| `tax_id` | `string` or `null` | No | CUIT/CUIL. Vacío se persiste como `null`. |
| `email` | `string` or `null` | No | Correo válido; se normaliza a minúsculas. |
| `phone` | `string` or `null` | No | Teléfono. |
| `address_street` | `string` or `null` | No | Calle. |
| `address_number` | `string` or `null` | No | Número. |
| `address_city` | `string` or `null` | No | Ciudad. |
| `address_postal_code` | `string` or `null` | No | Código postal. |
| `address_province` | `string` or `null` | No | Provincia. |
| `address_country` | `string` or `null` | No | País. |

#### Contrato de dirección

Los campos `address_*` (calle, número, ciudad, código postal, provincia y país)
son **independientes y opcionales**: no existe un objeto `address` anidado ni
obligación de completarlos en conjunto. Si un campo de texto se envía como
cadena vacía (`""`) se persiste como `NULL`; si se omite también queda `NULL`.

#### Valores de `type`

| Valor | Significado |
| --- | --- |
| `individual` | Autónomo o persona de actividad individual (por defecto). |
| `organization` | Comercio, emprendimiento o pequeña organización. |

Cualquier otro valor se rechaza con el error `Tipo de compañía inválido.`

#### Validación y errores de CUIT

El `tax_id` se valida **localmente**, sin depender de ARCA ni de ningún servicio
externo. La validación sólo comprueba la estructura: no implica que la compañía
esté verificada oficialmente ante ARCA.

Pasos aplicados sobre `tax_id` cuando se informa:

1. **Normalización:** se descartan guiones, puntos y espacios. Ej. `20-00000000-1`
   se normaliza a `20000000001`. Si el valor queda vacío tras normalizar, se
   persiste como `NULL`.
2. **Cantidad de dígitos:** debe tener exactamente 11 dígitos numéricos.
3. **Dígito verificador:** se aplica el algoritmo de CUIT/CUIL argentino (pesos
   `[5,4,3,2,7,6,5,4,3,2]` sobre los 10 primeros dígitos y cálculo del último).
4. **Duplicados:** si ya existe una compañía con ese CUIT normalizado, se
   rechaza (también garantizado por un `UniqueConstraint` en la base de datos).

Errores posibles (responden `400 Bad Request` con código `NEX-COM-001` y las
`errors` por campo):

- `El CUIT informado no es válido.` → estructura (dígitos / verificador) inválida
  o cantidad de dígitos incorrecta.
- `Ya existe una compañía registrada con ese CUIT.` → duplicado.

#### Ejemplo

```json
{
  "type": "organization",
  "name": "Org Ejemplo",
  "legal_name": "Org Ejemplo S.A.",
  "tax_id": "20-00000000-1",
  "email": "contacto@orgejemplo.com",
  "phone": "+54 11 5555 5555",
  "address_street": "Av. Ejemplo",
  "address_number": "123",
  "address_city": "Buenos Aires",
  "address_country": "Argentina"
}
```

#### Respuesta de ejemplo

```json
{
  "id": "d93d65eb-e066-4b94-a348-bab04448f0f0",
  "my_role": "owner",
  "type": "organization",
  "name": "Org Ejemplo",
  "legal_name": "Org Ejemplo S.A.",
  "tax_id": "20000000001",
  "email": "contacto@orgejemplo.com",
  "phone": "+54 11 5555 5555",
  "address_street": "Av. Ejemplo",
  "address_number": "123",
  "address_city": "Buenos Aires",
  "address_postal_code": null,
  "address_province": null,
  "address_country": "Argentina",
  "is_active": true,
  "created_at": "2026-10-10T12:00:00Z",
  "updated_at": "2026-10-10T12:00:00Z"
}
```

### Búsqueda (GET /api/companies/search/?q=...)

Localiza compañías por nombre, razón social o CUIT:

- la búsqueda sobre nombre y razón social usa coincidencia parcial sin distinguir
  mayúsculas de minúsculas;
- la búsqueda por CUIT normaliza el término antes de consultar, tolerando
  guiones, puntos y espacios;
- una búsqueda sin coincidencias devuelve una colección vacía (`200`, `[]`);
- una consulta `q` ausente o vacía se maneja de forma controlada devolviendo una
  colección vacía (`200`, `[]`).
- por defecto sólo devuelve Companies activas; admite los mismos filtros
  `is_active` y `type` que el listado.
- cada resultado incluye `my_role` correspondiente a la membresía del usuario.

#### Ejemplo de respuesta

```json
[
  {
    "id": "d93d65eb-e066-4b94-a348-bab04448f0f0",
    "my_role": "member",
    "type": "individual",
    "name": "María Pérez",
    "legal_name": null,
    "tax_id": null,
    "email": null,
    "phone": null,
    "address_street": null,
    "address_number": null,
    "address_city": null,
    "address_postal_code": null,
    "address_province": null,
    "address_country": null,
    "is_active": true,
    "created_at": "2026-10-10T12:00:00Z",
    "updated_at": "2026-10-10T12:00:00Z"
  }
]
```

### Detalle, edición y baja lógica

`GET /api/companies/{id}/` permite consultar una Company activa o inactiva a sus
miembros y devuelve `my_role`. `PUT` y `PATCH` sólo están disponibles para el rol
`owner` y mientras la Company permanezca activa. `DELETE` aplica la baja lógica
(`is_active = False`) y también requiere `owner`; conserva los datos y las
membresías.

Un usuario `member` puede consultar y buscar Companies a las que pertenece, pero
recibe `403 Forbidden` al intentar editarlas o darlas de baja. Las operaciones
de escritura sobre una Company inactiva también responden `403`. Las respuestas
de validación conservan `NEX-COM-001`; un UUID inexistente o ajeno responde
`404` con `NEX-COM-004`. La autenticación ausente o inválida responde `401` con
el error estándar de Bearer.

### Administración de miembros

Los miembros son usuarios existentes asociados mediante `CompanyMember`. Los
roles disponibles son `owner` y `member`. Un `owner` puede agregar miembros,
cambiar el rol de otro miembro y desvincular miembros; `owner` y `member` pueden
consultar la lista. Las operaciones que cambian membresías sólo funcionan
mientras la Company está activa. La lista sigue disponible para lectura
histórica si está inactiva.

#### Consultar miembros

`GET /api/companies/{id}/members/` devuelve `200 OK` con una lista. Cada fila
contiene el UUID, correo, nombre, apellido y rol del usuario. No devuelve campos
de autenticación ni privilegios globales.

```json
[
  {
    "user_id": "6fbf93aa-b5b3-44db-a798-e0eb4837737a",
    "email": "colaborador@example.com",
    "first_name": "Ana",
    "last_name": "García",
    "role": "member"
  }
]
```

#### Agregar un miembro

`POST /api/companies/{id}/members/` permite indicar exactamente uno de estos
identificadores: `email` (recomendado para PortalWeb y Mobile) o `user_id` (por
compatibilidad con clientes existentes). El usuario debe estar registrado y
activo en NexusBack. No se crea una cuenta ni se consulta Supabase Auth.

El correo se normaliza quitando espacios exteriores y se busca sin distinguir
mayúsculas/minúsculas. Si no existe un usuario activo, la coincidencia no es
única o ya tiene una membresía en la Company, se rechaza con el error genérico
`NEX-COM-001`. El campo `role` es opcional y por defecto usa `member`; para
asignar `owner` debe enviarse explícitamente.

Solicitud recomendada:

```json
{
  "email": "colaborador@ejemplo.com"
}
```

Solicitud compatible por UUID:

```json
{
  "user_id": "6fbf93aa-b5b3-44db-a798-e0eb4837737a",
  "role": "member"
}
```

Si se envían `email` y `user_id` juntos, la solicitud se rechaza. La respuesta
es `201 Created` con la fila de miembro (`user_id`, `email`, `first_name`,
`last_name`, `role`). La restricción única de la base de datos sigue impidiendo
duplicar una membresía.

La columna `User.email` tiene unicidad exacta, pero no insensible a mayúsculas.
Por eso pueden existir perfiles cuyos correos difieran sólo en capitalización.
El alta por correo detecta y rechaza esa ambigüedad; no elige un perfil
arbitrariamente. No se agregó índice ni migración.

El registro sincroniza el perfil local de User después de registrar la cuenta
en Supabase Auth. La incorporación sólo resuelve perfiles locales existentes;
si la cuenta no tiene perfil local o está inactiva, el alta se rechaza. La
API de Company no consulta ni repara identidades de Supabase que no tengan perfil
local. La asociación es inmediata: esta versión no envía invitaciones ni
requiere aceptación del colaborador.

#### Cambiar el rol

`PATCH /api/companies/{id}/members/{user_id}/` acepta el rol nuevo y devuelve
`200 OK` con la membresía resultante. Sólo un `owner` puede cambiar el rol de
otro miembro. Enviar el rol actual devuelve la membresía sin actualizarla.
Una Company debe conservar al menos un `owner`.

```json
{
  "role": "owner"
}
```

#### Desvincular un miembro

`DELETE /api/companies/{id}/members/{user_id}/` responde `204 No Content`. Sólo
un `owner` puede usarlo y la operación no elimina el perfil `User`, sus otras
membresías ni los datos de la Company. No se permite quitar al último `owner`.
Las escrituras bloquean la fila de Company dentro de una transacción para
serializar cambios de rol y bajas concurrentes.

#### Permisos, errores y límite de identificación

- Sin autenticación: `401` con el error estándar de Bearer.
- Company inexistente o ajena, o UUID que no pertenece a la Company: `404` con
  `NEX-COM-004`.
- `member` que intenta escribir, o escritura en Company inactiva: `403`.
- Datos inválidos, rol no permitido, usuario inexistente/inactivo/ambiguo,
  duplicado o intento de dejar la Company sin `owner`: `400` con `NEX-COM-001`.
- Los errores de usuario no distinguen existencia, estado, ambigüedad ni
  duplicación para no permitir usar el alta como búsqueda de usuarios.

La API actual de Users no ofrece a un `owner` un directorio de usuarios:
`GET /api/users/` y `GET /api/users/search/` requieren administración global. El
detalle de otro perfil también está restringido. Por eso, el alta por correo
evita que PortalWeb necesite conocer previamente el UUID, aunque Company no
ofrece autocompletado ni búsqueda global. El usuario debe compartir su correo de
registro por un canal confiable. La asociación es inmediata para cualquier
cuenta activa cuyo correo conozca el `owner`; no hay invitación ni aceptación
del colaborador.

## Criterios de diseño

- La migración puede ejecutarse correctamente contra PostgreSQL.
- Una compañía puede existir sin `tax_id` (CUIT) ni `legal_name` (razón
  social).
- El modelo diferencia actividades individuales de organizaciones mediante
  `type`.
- La baja lógica con `is_active` conserva la fila, las membresías y las
  relaciones existentes.
