# Módulo `cloud`

## Finalidad

`cloud/files` gestiona archivos asociados a una Company. La metadata se persiste
en Django y el contenido físico se guarda en el bucket privado `documents` de
Supabase Storage.

## Modelo actual

La tabla `documents` contiene los siguientes campos:

| Campo | Descripción |
| --- | --- |
| `id` | UUID y clave primaria. |
| `company_id` | Clave foránea a la Company asociada. |
| `name` | Nombre visible del documento. |
| `original_name` | Nombre original del archivo. |
| `storage_key` | Identificador interno de almacenamiento. |
| `mime_type` | Tipo MIME del archivo. |
| `size` | Tamaño del archivo en bytes. |
| `category_id` | UUID nullable, sin foreign key por ahora. |
| `created_at`, `updated_at` | Timestamps administrados por Django. |

`storage_key` es interno y no se expone en las respuestas públicas. El nombre
visible puede cambiar sin modificar esa clave.

## Storage

`POST /api/cloud/files/` sube el archivo al bucket privado `documents` antes de
persistir su metadata. La clave interna sigue la forma
`<company_uuid>/<document_uuid>` y no se expone públicamente.

## Endpoints actuales

Todas las operaciones requieren autenticación Bearer. Para acceder a una
Company, el usuario debe tener una membresía `CompanyMember`; los roles `owner`
y `member` tienen las mismas operaciones disponibles en Cloud. Los accesos sin
membresía responden `403 Forbidden`.

### Listado

`GET /api/cloud/files/?company_id=<uuid>`

Acepta opcionalmente `q` y `category_id`. Busca de forma parcial y sin distinguir
mayúsculas/minúsculas en `name` y `original_name`, permite filtrar por categoría
y ordena por `created_at` descendente.

### Creación

`POST /api/cloud/files/`

Requiere autenticación Bearer y recibe `multipart/form-data` con `company_id`,
`file`, `category_id` opcional y `name` opcional. Cuando no se informa `name`,
se usa el nombre original del archivo. El usuario debe pertenecer a la Company y
ésta debe estar activa; se rechaza la operación antes de subir el archivo cuando
alguna condición no se cumple.

El archivo debe contener datos, no puede superar 6 MiB y su tipo MIME declarado
debe ser uno de: PDF, JPEG, PNG, DOCX o XLSX. Esta restricción usa el MIME
informado por la carga; no verifica el contenido real del archivo.

### Edición de metadata

`PATCH /api/cloud/files/<id>/?company_id=<uuid>`

Sólo permite editar `name` y `category_id`. Cambiar `name` no renombra el archivo
físico; el resto de los campos permanece protegido. Requiere membresía y que la
Company esté activa. `company_id` no puede reasignarse mediante esta operación.

El ViewSet no expone una operación de eliminación de documentos.

### Descarga

`GET /api/cloud/files/<id>/download/`

Requiere autenticación Bearer y membresía en la Company real del documento. Devuelve
`{"url": "<signed-url>"}` con una URL temporal de 60 segundos para descargar desde
el bucket privado `documents`; no expone `storage_key`.

### Uso

`GET /api/cloud/files/usage/?company_id=<uuid>`

Responde `used`, `limit` y `available`, todos expresados en bytes.
Requiere membresía en la Company indicada. La consulta histórica permanece
disponible aunque la Company esté inactiva.

## Lectura de archivos XLSX

Los archivos con extensión `.xlsx` pueden consultarse después de validar la
membresía del usuario en la Company propietaria, incluso si está inactiva:

- `GET /api/cloud/files/<id>/sheets/` devuelve `{"sheets": ["Clientes"]}`.
- `GET /api/cloud/files/<id>/sheets/<hoja>/` devuelve el nombre y las filas de
  la hoja como valores JSON.

Las fechas se serializan con el formato ISO 8601 de la API. Las fórmulas no se
calculan; se devuelve el valor guardado en el libro, o `null` si no tiene uno.

## Variables de entorno

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `DOCUMENT_MAX_SIZE_MB`
- `DOCUMENT_COMPANY_LIMIT_MB`
- `DOCUMENT_STORAGE_SAFE_LIMIT_MB`

## Errores

`NEX-DOC-001` identifica datos de entrada inválidos, `NEX-DOC-002` un documento
no encontrado o no disponible para la Company indicada y `NEX-DOC-003` un fallo
de Storage. El catálogo completo está en [docs/ERROR_CODES.md](../ERROR_CODES.md).
La ausencia de autenticación responde `401`; la falta de membresía o los intentos
de escritura sobre una Company inactiva responden `403`.

## Pendiente / fuera de alcance actual

- Cuota por Company.
- Eliminación de documentos y de sus archivos físicos.
- Consistencia entre DB y Storage si falla la persistencia posterior al upload.
