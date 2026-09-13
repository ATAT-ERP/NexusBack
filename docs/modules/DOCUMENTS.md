# Módulo `documents`

## Finalidad

`documents` gestiona archivos asociados a una Company. La metadata se persiste
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

`POST /api/documents/` sube el archivo al bucket privado `documents` antes de
persistir su metadata. La clave interna sigue la forma
`<company_uuid>/<document_uuid>` y no se expone públicamente.

## Endpoints actuales

### Listado

`GET /api/documents/?company_id=<uuid>`

Acepta opcionalmente `q` y `category_id`. Busca de forma parcial y sin distinguir
mayúsculas/minúsculas en `name` y `original_name`, permite filtrar por categoría
y ordena por `created_at` descendente.

### Creación

`POST /api/documents/`

Requiere autenticación Bearer y recibe `multipart/form-data` con `company_id`,
`file`, `category_id` opcional y `name` opcional. Cuando no se informa `name`,
se usa el nombre original del archivo.

El archivo debe contener datos, no puede superar 6 MiB y su tipo MIME declarado
debe ser uno de: PDF, JPEG, PNG, DOCX o XLSX. Esta restricción usa el MIME
informado por la carga; no verifica el contenido real del archivo.

### Edición de metadata

`PATCH /api/documents/<id>/?company_id=<uuid>`

Sólo permite editar `name` y `category_id`. Cambiar `name` no renombra el archivo
físico; el resto de los campos permanece protegido.

### Descarga

`GET /api/documents/<id>/download/`

Requiere autenticación Bearer y membership en la Company real del documento. Devuelve
`{"url": "<signed-url>"}` con una URL temporal de 60 segundos para descargar desde
el bucket privado `documents`; no expone `storage_key`.

### Uso

`GET /api/documents/usage/?company_id=<uuid>`

Responde `used`, `limit` y `available`, todos expresados en bytes.

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

## Pendiente / fuera de alcance actual

- Cuota por Company.
- Eliminación física.
- Consistencia entre DB y Storage si falla la persistencia posterior al upload.
- Permisos owner/member y categorías completas.
