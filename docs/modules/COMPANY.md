# Módulo `company`

## Finalidad

`company` representa el espacio de trabajo de una actividad económica dentro
de A.T.A.T., pudiendo corresponder a un autónomo, comercio, emprendimiento o
pequeña organización. La compañía no requiere validación fiscal externa para
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
├── migrations/
│   ├── 0001_initial.py
│   └── 0002_company_unique_company_tax_id.py
├── tests.py
├── apps.py
└── models.py
```

## Endpoints actuales

```text
POST  /api/companies/
GET   /api/companies/search/?q=...
```

Ningún endpoint de `company` exige autenticación en la versión actual. No existen
todavía operaciones de detalle, edición ni de activar/desactivar compañías.

### Alta (POST /api/companies/)

Registra una nueva compañía. Responde `201 Created` con el cuerpo de la compañía
creada (incluye su `id`), o `400 Bad Request` cuando falla la validación.

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

### Búsqueda (GET /api/companies/search/?q=...)

Localiza compañías por nombre, razón social o CUIT:

- la búsqueda sobre nombre y razón social usa coincidencia parcial sin distinguir
  mayúsculas de minúsculas;
- la búsqueda por CUIT normaliza el término antes de consultar, tolerando
  guiones, puntos y espacios;
- una búsqueda sin coincidencias devuelve una colección vacía (`200`, `[]`);
- una consulta `q` ausente o vacía se maneja de forma controlada devolviendo una
  colección vacía (`200`, `[]`).

## Criterios de diseño

- La migración puede ejecutarse correctamente contra PostgreSQL.
- Una compañía puede existir sin `tax_id` (CUIT) ni `legal_name` (razón
  social).
- El modelo diferencia actividades individuales de organizaciones mediante
  `type`.
- La baja futura se resuelve mediante `is_active` sin eliminar registros:
  desactivar (`is_active = False`) da de baja la compañía conservando la fila.
