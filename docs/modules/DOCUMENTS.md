# Módulo `documents`

## Finalidad

`documents` gestiona la metadata de archivos asociados a una Company. No es una
nube tipo Drive: el almacenamiento físico todavía no está conectado.

El módulo está implementado parcialmente. `company_id` sigue siendo un UUID sin
clave foránea real; la integración con Supabase Storage y los permisos de
owner/member permanecen pendientes.

## Modelo actual

La tabla `documents` contiene los siguientes campos:

| Campo | Descripción |
| --- | --- |
| `id` | UUID y clave primaria. |
| `company_id` | UUID de la Company, sin foreign key por ahora. |
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

Existe la abstracción `FileStorage`, que hoy sólo define el contrato de
almacenamiento. No hay una implementación concreta ni integración con Supabase
Storage.

## Endpoints actuales

### Listado

`GET /api/documents/?company_id=<uuid>`

Acepta opcionalmente `q` y `category_id`. Busca de forma parcial y sin distinguir
mayúsculas/minúsculas en `name` y `original_name`, permite filtrar por categoría
y ordena por `created_at` descendente.

### Edición de metadata

`PATCH /api/documents/<id>/?company_id=<uuid>`

Sólo permite editar `name` y `category_id`. Cambiar `name` no renombra el archivo
físico; el resto de los campos permanece protegido.

### Uso

`GET /api/documents/usage/?company_id=<uuid>`

Responde `used`, `limit` y `available`, todos expresados en bytes.

## Límites MVP

- Máximo previsto por archivo: 6 MiB.
- Máximo por Company: 12 MiB.
- Límite interno seguro: 40 MiB.

El máximo de 6 MiB todavía no se valida porque upload no existe. El límite de
12 MiB todavía no bloquea operaciones y el límite interno de 40 MiB no se expone
al consumidor. Los tres se utilizarán durante la implementación futura de upload.

## Variables de entorno

- `DOCUMENT_MAX_SIZE_MB`
- `DOCUMENT_COMPANY_LIMIT_MB`
- `DOCUMENT_STORAGE_SAFE_LIMIT_MB`

## Errores

`NEX-DOC-001` identifica datos de entrada inválidos y `NEX-DOC-002` un documento
no encontrado o no disponible para la Company indicada. El catálogo completo está
en [docs/ERROR_CODES.md](../ERROR_CODES.md).

## Pendiente / fuera de alcance actual

- Supabase Storage y bucket privado.
- Upload, validación efectiva de 6 MiB y cuota por Company.
- Límite seguro global, download y eliminación definitiva.
- Consistencia entre base de datos y Storage.
- Permisos, integración real con Company y categorías completas.
