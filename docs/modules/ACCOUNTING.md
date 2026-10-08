# Módulo `accounting`

## Finalidad

`accounting` mantiene el registro contable histórico de una Company: plan de
cuentas, asientos y movimientos. Los asientos publicados son inmutables y las
reversiones se conservan como asientos nuevos, de modo que el efecto económico
final siempre pueda reconstruirse a partir de los movimientos registrados.

La información histórica se consulta directamente sobre `JournalEntry`,
`JournalLine` y `Account`: no existen modelos, saldos almacenados ni tablas
propias de reportes. Cada consulta contable se calcula en el momento de la
petición.

El label de la aplicación Django es `accounting` (`apps.accounting`).

## Modelo actual

### Account (`accounting_accounts`)

| Campo | Descripción |
| --- | --- |
| `id` | Clave primaria entera. |
| `company` | Clave foránea a la Company propietaria del plan de cuentas. |
| `code` | Código de la cuenta; único dentro de la Company. |
| `name` | Nombre de la cuenta. |
| `account_type` | `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE` o `EXPENSE`. |
| `is_active` | Las cuentas inactivas no reciben movimientos normales; pueden reutilizarse en una reversión interna. |
| `created_at`, `updated_at` | Timestamps administrados por Django. |

### JournalEntry (`accounting_journal_entries`)

| Campo | Descripción |
| --- | --- |
| `company` | Clave foránea a la Company del asiento. |
| `number` | Número correlativo asignado por Company al crear; no editable. |
| `accounting_date` | Fecha contable del asiento. |
| `description` | Concepto del asiento. |
| `status` | `DRAFT` (defecto), `POSTED` o `REVERSED`. |
| `source_type` | Origen: `MANUAL` (defecto), `INVOICE`, `PAYMENT` o `IMPORT`. |
| `source_id` | Identificador del origen, opcional. |
| `currency` | Moneda; actualmente sólo `ARS`. |
| `created_by` | Usuario que registró el asiento; puede ser `null`. |
| `reversal_of` | Asiento revertido por éste; sólo en las reversiones. |
| `metadata` | JSON opcional. |
| `created_at`, `updated_at` | Timestamps administrados por Django. |

Restricciones: `number` es único por Company y `(company, source_type,
source_id)` es único cuando `source_id` está informado.
Una vez creado el asiento, `number` y `company` no pueden modificarse mediante
`save()`, `update()` ni `bulk_update()`. La numeración se asigna exclusivamente
durante la creación normal; `bulk_create()` no está soportado para asientos.

### JournalLine (`accounting_journal_lines`)

| Campo | Descripción |
| --- | --- |
| `journal_entry` | Clave foránea al asiento; sus movimientos se eliminan en cascada. |
| `account` | Cuenta de la misma Company que el asiento; debe estar activa salvo en la reversión interna. |
| `description` | Concepto del movimiento. |
| `debit` | Importe del Debe; `0` cuando el movimiento es de Haber. |
| `credit` | Importe del Haber; `0` cuando el movimiento es de Debe. |

Una fila no puede tener Debe y Haber a la vez ni ambos en cero (constraint
`journal_line_debit_or_credit`).

## Estados del asiento

```text
DRAFT ──publish──▶ POSTED ──reverse──▶ REVERSED
```

| Estado | Significado |
| --- | --- |
| `DRAFT` | Borrador editable y eliminable. No integra el historial ni afecta ningún reporte contable. |
| `POSTED` | Publicado: inmutable y parte del historial contable válido. |
| `REVERSED` | Asiento original de una reversión. Se conserva con sus movimientos; la reversión publicada los refleja en espejo. |

Las transiciones sólo pueden ejecutarse mediante los services de publicación y
reversión: ni `save()` ni el ORM permiten cambiar el estado.

## Estructura actual

```text
apps/accounting/
├── enums/
│   ├── account_type.py
│   ├── currency.py
│   ├── entry_origin.py
│   └── entry_status.py
├── migrations/
├── models/
│   ├── account.py
│   ├── journal_entry.py
│   └── journal_line.py
├── serializers/
│   ├── account.py
│   └── journal_entry.py
├── services/
│   └── journal_entry.py
├── tests/
│   ├── test_accounts.py
│   ├── test_journal_entries.py
│   ├── test_journal_entry_publication.py
│   ├── test_journal_entry_reversal.py
│   └── test_reports.py
├── apps.py
├── urls.py
└── views.py
```

## Endpoints actuales

```text
GET    /api/accounting/companies/<uuid>/accounts/
POST   /api/accounting/companies/<uuid>/accounts/
GET    /api/accounting/companies/<uuid>/accounts/<id>/
PATCH  /api/accounting/companies/<uuid>/accounts/<id>/

POST   /api/accounting/companies/<uuid>/journal-entries/<id>/publish/
POST   /api/accounting/companies/<uuid>/journal-entries/<id>/reverse/

GET    /api/accounting/companies/<uuid>/journal-entries/
GET    /api/accounting/companies/<uuid>/journal-entries/<id>/
GET    /api/accounting/companies/<uuid>/reports/daily-journal/
GET    /api/accounting/companies/<uuid>/reports/general-ledger/<account_id>/
GET    /api/accounting/companies/<uuid>/reports/trial-balance/
```

Todos exigen `Authorization: Bearer <access_token>` y membership del usuario en
la Company de la URL; sin membership la respuesta es `403 Forbidden`. No existe
paginación: los listados devuelven colecciones planas.

Todavía no hay endpoints para crear ni editar asientos y movimientos: hoy sólo
se crean desde el ORM y los services del módulo.

### Plan de cuentas

- `GET .../accounts/` lista las cuentas ordenadas por `code`; acepta los filtros
  opcionales `account_type` e `is_active`.
- `POST .../accounts/` crea una cuenta dentro de la Company de la URL. El
  `code` debe ser único por Company (`400` si se repite); el `company` enviado en
  el body se ignora.
- `GET/PATCH .../accounts/<id>/` consulta o actualiza una cuenta. No existe
  `DELETE` (`405`); la baja se hace con `is_active = false`.

### Publicación y reversión de asientos

- `POST .../journal-entries/<id>/publish/` publica un borrador y responde
  `200` con `{"id", "number", "status"}`. Valida que tenga al menos dos
  movimientos, que todas las cuentas pertenezcan a la Company y estén activas y
  que la suma del Debe sea igual a la del Haber; cualquier incumplimiento
  responde `400` y el asiento sigue en `DRAFT`.
- `POST .../journal-entries/<id>/reverse/` crea y publica el asiento espejo
  (importes intercambiados, `accounting_date` del día, `reversal_of` apuntando al
  original) y marca el original como `REVERSED`. Responde `200` con el asiento de
  reversión. Sólo acepta asientos `POSTED`.
  La reversión reutiliza las cuentas originales aunque estén inactivas, sin
  reactivarlas. Esta excepción pertenece al flujo interno de reversión:
  los movimientos normales y `publish_journal_entry()` siguen exigiendo cuentas
  activas; informar `reversal_of` por sí solo no habilita la excepción.

## Consultas contables

Las cuatro consultas se limitan a la Company de la URL y consideran únicamente
el historial contable válido: los asientos en `DRAFT` nunca aparecen ni afectan
los resultados.

Fechas: todos los rangos usan los parámetros opcionales `accounting_date_from` y
`accounting_date_to` en formato ISO (`YYYY-MM-DD`); sin ellos se considera todo
el historial. Un valor inválido responde `400 Bad Request`.

### Historial de asientos

`GET .../journal-entries/`

Devuelve los asientos de la Company en orden cronológico (`accounting_date`,
luego `number`). Admite además los filtros `status` (`DRAFT`, `POSTED` o
`REVERSED`; `DRAFT` siempre devuelve `[]`) y `source_type` (`MANUAL`,
`INVOICE`, `PAYMENT`, `IMPORT`).

```json
[
  {
    "id": 1,
    "number": 1,
    "accounting_date": "2026-01-10",
    "description": "Compra de insumos",
    "status": "POSTED",
    "source_type": "MANUAL",
    "source_id": null,
    "currency": "ARS",
    "created_by": null,
    "reversal_of": null,
    "metadata": null,
    "created_at": "2026-01-10T12:00:00+00:00",
    "updated_at": "2026-01-10T12:00:00+00:00"
  }
]
```

`GET .../journal-entries/<id>/`

Devuelve los mismos campos del asiento más sus movimientos. Un asiento borrador
o de otra Company responde `404`. Ejemplo abreviado:

```json
{
  "id": 1,
  "number": 1,
  "status": "POSTED",
  "lines": [
    {
      "id": 1,
      "account": 10,
      "account_code": "1.1.01",
      "account_name": "Caja",
      "description": "Compra de insumos",
      "debit": "100.00",
      "credit": "0.00"
    }
  ]
}
```

### Libro Diario

`GET .../reports/daily-journal/`

Consulta cronológica de los asientos del historial dentro del rango, con el
mismo formato del detalle: número, fecha contable, concepto y movimientos con
cuenta, Debe y Haber. Ejemplo abreviado:

```json
[
  {
    "number": 1,
    "accounting_date": "2026-01-10",
    "description": "Compra de insumos",
    "lines": [
      {"account_code": "1.1.01", "debit": "100.00", "credit": "0.00"},
      {"account_code": "5.1.01", "debit": "0.00", "credit": "100.00"}
    ]
  }
]
```

### Libro Mayor

`GET .../reports/general-ledger/<account_id>/`

Movimientos de una cuenta dentro del rango, en orden cronológico, con el saldo
acumulado de cada fila. El saldo se acumula sobre todo el historial: si el rango
comienza en una fecha posterior al primer movimiento, la primera fila parte del
saldo acumulado hasta ese momento. La cuenta debe pertenecer a la Company de la
URL (`404` en caso contrario).

```json
[
  {
    "accounting_date": "2026-02-10",
    "entry_number": 2,
    "description": "Venta de mercadería",
    "debit": "0.00",
    "credit": "60.00",
    "balance": "40.00"
  }
]
```

### Sumas y Saldos

`GET .../reports/trial-balance/`

Agrega los movimientos del rango por cuenta: sólo aparecen las cuentas con
movimientos y los resultados se calculan en cada petición, sin persistencia.

```json
[
  {
    "account": 10,
    "code": "1.1.01",
    "name": "Caja",
    "total_debit": "100.00",
    "total_credit": "60.00",
    "balance": "40.00"
  }
]
```

Los importes de todas las respuestas se serializan como cadena con dos
decimales y `balance` es `total_debit - total_credit`.

## Errores

El módulo no tiene códigos `NEX-*` propios: responde con los errores estándar
de DRF (`400` validación, `401` sin Bearer, `403` sin membership, `404` recurso
inexistente o fuera de la Company, `405` método no permitido).

## Pendiente / fuera de alcance actual

- Creación y edición de asientos y movimientos por API.
- Estados contables legales, balance general formal y estado de resultados.
- Cierres mensuales y anuales.
- Conciliación bancaria y reportes fiscales.
- Exportación a Excel/PDF e integración con Cloud.
- Paginación de los listados.
