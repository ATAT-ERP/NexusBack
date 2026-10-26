# Representaciones de Billing en Cloud

La configuración fiscal, los comprobantes y el flujo de emisión se documentan
en [BILLING.md](BILLING.md). Este documento concentra su integración con Cloud.

## Auditoría y punto de integración

- `apps/cloud/models.py`: `File` pertenece a una Company mediante FK protegida.
  Cloud administra nombre, MIME, tamaño, clave de Storage y fechas.
- `apps/cloud/files/storage.py`: cliente Supabase existente; el bucket privado
  `documents` y las operaciones físicas permanecen dentro de Cloud.
- `FileCreateSerializer`: admite PDF, valida archivo no vacío y máximo de 6 MiB
  por defecto (`DOCUMENT_MAX_SIZE_BYTES`).
- `DOCUMENT_COMPANY_LIMIT_BYTES` se informa en `usage`; actualmente Cloud no
  impone cuotas por Company ni el límite global de Storage. Esta integración
  conserva esas reglas y no implementa un sistema paralelo de cuotas.
- La carga exige `CompanyMember` y Company activa, tanto para `owner` como
  para `member`. La consulta y descarga históricas admiten Company inactiva.
- `FileViewSet.download` comprueba membership sobre la Company real del archivo
  antes de generar una signed URL de 60 segundos.

El punto compartido es `apps/cloud/files/services.py`: se extrajo la creación
existente para que la API multipart y Billing usen las mismas validaciones,
permisos, carga, metadata y compensación ante fallos de persistencia.
Billing no importa el cliente de Storage ni genera signed URLs.

## Formato e historial

Se usa PDF: es imprimible y Cloud ya lo admite. ReportLab, incluido en las
dependencias del proyecto, pagina texto variable y tablas.

El PDF contiene tipo, número, fecha, snapshots del emisor y receptor, ítems,
condiciones tributarias y totales persistidos. En facturas incluye concepto,
fechas opcionales de servicio/vencimiento y detalle de IVA. En NC incluye las
facturas acreditadas y sus ítems e importes. No consulta datos actuales de la
Company para representar al emisor ni recalcula totales. No incorpora ARCA.

`Invoice.representation_file` y `CreditNote.representation_file` son relaciones
opcionales OneToOne a `File`, protegidas y no editables por la API. No guardan
binarios ni duplican metadata de Cloud.

## API

Las dos rutas requieren Bearer y membership según las reglas de Billing:

- `/api/billing/companies/<company_id>/invoices/<pk>/representation/`
- `/api/billing/companies/<company_id>/credit-notes/<pk>/representation/`

`POST` solicita la representación: responde `201` si se creó o `200` si ya
existía. No requiere payload. Bloquea la fila del comprobante para que solicitudes
simultáneas reutilicen el mismo archivo. Rechaza borradores con `400`. Las
facturas canceladas por una NC conservan su representación histórica.

`GET` consulta la representación sin generar archivos ni acceder a Storage.
Responde `200` si existe, `404` si falta y `400` para borradores.

Ambos métodos responden:

```json
{
  "file": {"id": "<uuid>", "company_id": "<uuid>", "name": "invoice-00001-00000001.pdf", "...": "metadata pública de FileSerializer"},
  "download_url": "/api/cloud/files/<uuid>/download/"
}
```

`download_url` es la ruta protegida existente de Cloud, no una URL de Storage.
El cliente debe solicitarla con Bearer para obtener la signed URL; Cloud vuelve
a verificar membership en ese momento.

## Fallos y reintentos

La emisión no genera archivos ni llama a Cloud. Se solicita la representación
en otra operación después de emitir. Un fallo no modifica estado, número,
snapshot ni secuencia del comprobante. No hay generación automática ni worker.

La view traduce `StorageException` y `httpx.RequestError` a `502` con
`NEX-DOC-003`; `LayoutError`, `ValueError` y `DatabaseError` a `500` con
`NEX-BIL-001`. Estas respuestas incluyen `code` y `message`, según
[ERROR_CODES.md](../ERROR_CODES.md). Las demás excepciones siguen el manejo
estándar; no se captura cualquier fallo como error de representación.
Los errores de validación de Cloud se conservan como `400`.
Se puede reintentar el mismo `POST`.

La asociación y la metadata se guardan en una transacción independiente de la
emisión. Si falla la persistencia se revierte la metadata y Cloud intenta limpiar
la carga física. Si también falla esa compensación, queda registrado en logs;
no existe una transacción distribuida entre PostgreSQL y Supabase.

Una Company inactiva puede consultar y reutilizar una representación existente,
pero Cloud rechaza nuevas cargas con `403`.

## Verificación

`apps/billing/tests/test_representation.py` cubre facturas, borradores,
asociación y reutilización, concurrencia con dos conexiones PostgreSQL,
errores y reintentos, límites por archivo, Company/membership, descarga por
Cloud, NC y facturas canceladas. La suite usa Storage simulado; no realiza
operaciones sobre un bucket real.
