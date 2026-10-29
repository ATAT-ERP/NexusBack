# Módulo `deadlines`

## Finalidad

`deadlines` permite a cada contador administrar una agenda de tareas y vencimientos
para sus clientes. Cada cliente es una `Company`, que puede representar una
persona individual o una organización. `CompanyMember` determina las compañías
a las que el usuario tiene acceso; las tareas siguen siendo privadas de su
propietario aunque varios usuarios compartan la misma compañía.

La aplicación Django es `apps.deadlines`, la tabla es `deadlines` y su migración
inicial es `apps/deadlines/migrations/0001_initial.py`.

## Modelo y representación

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `id` | UUID | Clave primaria generada automáticamente; solo lectura. |
| `owner` | UUID de usuario | Propietario obligatorio, asignado por el servidor al crear; solo lectura en la API. |
| `company` | UUID de Company | Cliente obligatorio. Al crear o cambiarlo debe ser una compañía activa con membresía del usuario. |
| `name` | string | Concepto obligatorio y no vacío, máximo 255 caracteres. |
| `period` | string o `null` | Período de referencia opcional, máximo 255 caracteres; se admite cadena vacía. |
| `due_date` | fecha | Vencimiento obligatorio en formato `YYYY-MM-DD`. |
| `status` | string | `pending` o `completed`; por defecto `pending`. |
| `notes` | string o `null` | Observaciones opcionales; se admite cadena vacía. |
| `created_at` | fecha y hora | Fecha automática de creación; solo lectura. |
| `updated_at` | fecha y hora | Fecha automática de última modificación; solo lectura. |
| `overdue` | boolean | Indicador calculado de vencimiento; solo lectura, no persistido. |
| `due_soon` | boolean | Indicador calculado de vencimiento próximo; solo lectura, no persistido. |

`owner` y `company` son relaciones obligatorias. La eliminación del usuario
elimina sus tareas en cascada; la eliminación física de una compañía con tareas
está protegida mediante `PROTECT`. Esto es distinto de desactivar una compañía.
Los únicos estados persistidos son `pending` y `completed`.

## Autenticación y acceso

Todas las operaciones requieren `Authorization: Bearer <access_token>` de
Supabase y un perfil local activo. El listado y el detalle incluyen únicamente
tareas cuyo `owner` es el usuario autenticado y cuya compañía conserva una
membresía `CompanyMember` de ese usuario. El rol de la membresía no restringe
estas operaciones.

- Una tarea de otro propietario no es visible, incluso si ambos pertenecen a
  la misma compañía. El acceso directo por ID responde `404`.
- Al revocar la membresía se pierde el acceso a las tareas de esa compañía,
  incluso si el usuario es su propietario. No se eliminan por ello.
- Una compañía inactiva conserva acceso de lectura a sus tareas mientras exista
  la membresía. Sus tareas no se pueden actualizar ni eliminar; esas operaciones
  responden `403`. Tampoco se puede crear una tarea en ella ni seleccionarla como
  destino al cambiar de compañía.
- El servidor asigna el `owner` a partir del usuario autenticado. Los campos de
  solo lectura enviados por el cliente, incluido `owner`, se ignoran.

## Endpoints

Las rutas usan barra final y todas las solicitudes con cuerpo usan
`Content-Type: application/json`.

| Método | Ruta | Resultado |
| --- | --- | --- |
| `GET` | `/api/deadlines/` | `200`: arreglo de tareas accesibles, sin paginación. |
| `POST` | `/api/deadlines/` | `201`: tarea creada. |
| `GET` | `/api/deadlines/{id}/` | `200`: detalle de la tarea accesible. |
| `PUT` | `/api/deadlines/{id}/` | `200`: actualización completa; requiere `company`, `name` y `due_date`. |
| `PATCH` | `/api/deadlines/{id}/` | `200`: actualización parcial. |
| `DELETE` | `/api/deadlines/{id}/` | `204`: eliminación física de la tarea, sin cuerpo. |

`{id}` es un UUID. En `PUT` los campos opcionales pueden omitirse; en `PATCH`
sólo es necesario enviar los campos que se desean cambiar. Para completar o
reabrir una tarea, enviar `status: "completed"` o `status: "pending"`.

### Crear una tarea

```http
POST /api/deadlines/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "company": "11111111-1111-4111-8111-111111111111",
  "name": "Presentar declaración",
  "period": "2026-11",
  "due_date": "2026-12-15",
  "notes": "Revisar documentación"
}
```

Ejemplo de respuesta `201`, suponiendo que la fecha de negocio es el
`2026-12-10`:

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "owner": "22222222-2222-4222-8222-222222222222",
  "company": "11111111-1111-4111-8111-111111111111",
  "name": "Presentar declaración",
  "period": "2026-11",
  "due_date": "2026-12-15",
  "status": "pending",
  "notes": "Revisar documentación",
  "created_at": "2026-12-10T12:00:00Z",
  "updated_at": "2026-12-10T12:00:00Z",
  "overdue": false,
  "due_soon": true
}
```

El mismo formato de objeto se devuelve en detalle, creación y actualización.
El listado devuelve un arreglo de esos objetos, o `[]` si no hay coincidencias.

### Listar y filtrar

```http
GET /api/deadlines/?company_id=11111111-1111-4111-8111-111111111111&status=pending&due_date_from=2026-12-01&due_date_to=2026-12-31
Authorization: Bearer <access_token>
```

| Parámetro opcional | Valor | Efecto |
| --- | --- | --- |
| `company_id` | UUID válido | Limita a esa compañía. Un UUID válido sin tareas accesibles devuelve `[]`. |
| `status` | `pending` o `completed` | Filtra por estado persistido. |
| `due_date_from` | `YYYY-MM-DD` | Incluye vencimientos desde esa fecha, inclusive. |
| `due_date_to` | `YYYY-MM-DD` | Incluye vencimientos hasta esa fecha, inclusive. |

Los filtros se pueden combinar. Sin filtros se listan todas las tareas accesibles,
incluidas las históricas de compañías inactivas con membresía vigente. El orden
es `due_date` ascendente y, para igual fecha, `id` ascendente. Los filtros no
amplían los permisos del usuario.

### Consultar, modificar y eliminar

```http
GET /api/deadlines/33333333-3333-4333-8333-333333333333/
Authorization: Bearer <access_token>
```

```http
PATCH /api/deadlines/33333333-3333-4333-8333-333333333333/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{"status": "completed"}
```

La respuesta `200` contiene la tarea actualizada; en este caso ambos indicadores
serán `false`. Para una actualización completa se utiliza `PUT` con, por ejemplo:

```json
{
  "company": "11111111-1111-4111-8111-111111111111",
  "name": "Declaración actualizada",
  "due_date": "2026-12-20",
  "status": "pending"
}
```

Para eliminarla se envía `DELETE` a la misma ruta de detalle con el Bearer; una
eliminación exitosa responde `204 No Content`.

## Indicadores calculados

La fecha de referencia se calcula en `America/Argentina/Buenos_Aires`, no según
la zona horaria del navegador. Los valores se calculan al serializar y no se
almacenan en la base de datos:

- `overdue`: `true` sólo si la tarea está `pending` y `due_date` es anterior a
  la fecha de referencia.
- `due_soon`: `true` sólo si está `pending` y vence entre hoy y siete días después,
  ambos inclusive.
- Para `completed`, ambos valores son `false`, independientemente de la fecha.
  Una tarea pendiente posterior al plazo de siete días también tiene ambos en `false`.

Los indicadores se devuelven también en las respuestas de creación y actualización;
no se pueden editar ni usar como filtros en este endpoint.

## Validaciones y errores

La API exige una compañía activa con membresía al crear o cambiar `company`,
además de `name` y `due_date`. Rechaza UUID, fechas o estados inválidos, campos
obligatorios ausentes y un rango con `due_date_from` posterior a `due_date_to`.
Un UUID de compañía válido pero ajeno o inactivo en una escritura produce `400`.

| HTTP | Situación |
| --- | --- |
| `400 Bad Request` | Datos o filtros inválidos; los errores DRF se agrupan por campo. |
| `401 Unauthorized` | Sin encabezado de autorización, DRF devuelve `detail`; si está mal formado o el Bearer es inválido, se devuelve `NEX-USR-010` con `message`. |
| `403 Forbidden` | Se intenta modificar una tarea de compañía inactiva, o la autenticación rechaza un perfil inactivo (`NEX-USR-002`). |
| `404 Not Found` | Con un UUID válido, la tarea no existe, pertenece a otro usuario o no hay membresía vigente; DRF devuelve `detail`. |

Por ejemplo, un rango invertido responde `400`:

```json
{"due_date_to": ["La fecha final debe ser igual o posterior a la inicial."]}
```

Los errores propios de `deadlines` usan principalmente el formato nativo de DRF;
el módulo no define códigos internos propios. La autenticación puede devolver
códigos compartidos, descritos en [Códigos de error](ERROR_CODES.md).
Un UUID inválido no coincide con la ruta y Django devuelve `404` antes de llegar
a DRF; su cuerpo no tiene garantizado el formato JSON del detalle de una tarea
inexistente o inaccesible.

## Alcance actual

El módulo no implementa estadísticas independientes, filtros por indicadores,
paginación, recurrencias, recordatorios ni notificaciones. Las rutas y los campos
anteriores están disponibles para su integración con PortalWeb.
