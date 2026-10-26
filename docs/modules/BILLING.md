# Módulo `billing`

## Finalidad

`apps/billing` administra la configuración fiscal de una Company, sus puntos de
venta, facturas A/B/C y notas de crédito (NC) A/B/C. Permite preparar borradores,
emitirlos con numeración interna, conservar snapshots y totales y solicitar una
representación PDF mediante Cloud.

La emisión implementada es interna. Los enums usan códigos fiscales de
AFIP/ARCA, pero no hay cliente ARCA, autenticación fiscal, solicitud de CAE ni
consulta o sincronización de numeración oficial. El PDF indica expresamente
que es una representación interna sin autorización fiscal ARCA.

## Modelo actual

Las claves primarias de Billing son enteras; `Company` se identifica con UUID.
La pertenencia de los comprobantes se resuelve por
`point_of_sale → fiscal_profile → company`.

| Modelo / tabla | Campos y relaciones relevantes |
| --- | --- |
| `FiscalProfile` / `billing_fiscal_profiles` | OneToOne `company`; `vat_condition` obligatorio; `gross_income` opcional (cadena vacía por defecto), `business_start_date` opcional y nullable; timestamps. |
| `PointOfSale` / `billing_points_of_sale` | FK `fiscal_profile`; `number` entero único por perfil; `is_active = true` por defecto; timestamps. `formatted_number` lo representa con un mínimo de cinco dígitos. |
| `InvoiceSequence` / `billing_invoice_sequences` | FK `point_of_sale`; `invoice_type` admite tipos de factura y NC; `last_number = 0` inicialmente. Única por punto y tipo. No tiene API pública. |
| `Invoice` / `billing_invoices` | FK `point_of_sale`; `invoice_type`, `status`, `number`, `issue_date`, `concept`, fechas opcionales de servicio y vencimiento, datos del receptor, totales, snapshot del emisor, representación y timestamps. |
| `InvoiceItem` / `billing_invoice_items` | FK `invoice`; `description` (255 caracteres), `quantity`, `unit_price`, `discount = 0`, `tax_treatment` y `vat_rate` opcional/nullable. |
| `InvoiceTax` / `billing_invoice_taxes` | FK `invoice`; `tax_type`, `vat_rate`, `base_amount`, `amount`. Detalle generado al emitir; único por factura, tipo y alícuota. |
| `CreditNote` / `billing_credit_notes` | FK `point_of_sale`; `credit_note_type`, `status`, `number`, `issue_date`, datos del receptor, totales, snapshot del emisor, representación y timestamps. Relación M2M con facturas mediante `CreditNoteInvoice`. |
| `CreditNoteInvoice` / `billing_credit_note_invoices` | FK `credit_note`, FK protegida `invoice` y `total` acreditado (0 por defecto, constraint `>= 0`). Par NC/factura único. |
| `CreditNoteItem` / `billing_credit_note_items` | FK `credit_note_invoice`; mismos campos de descripción, cantidades, precios, descuento y tratamiento fiscal que `InvoiceItem`. |

Los datos generales del emisor permanecen en Company, sin duplicarse en el
perfil fiscal. Los comprobantes conservan estos campos históricos al emitir:
`issuer_legal_name`, `issuer_tax_id`, `issuer_address`, `issuer_vat_condition`,
`issuer_gross_income` e `issuer_activity_start_date`.

Los datos del receptor son `receiver_name`, `receiver_vat_condition`,
`receiver_document_type`, `receiver_document_number` y `receiver_address`.
Se ingresan en la factura; en una NC los copia el backend al emitir.

Facturas y NC almacenan `net_taxed`, `net_untaxed`, `net_exempt`, `vat_amount`
y `total`, todos Decimal de 14 dígitos y dos decimales, inicialmente cero.
`quantity` admite 10 dígitos y dos decimales; `unit_price`, 14 y dos;
`discount`, cinco y dos. Ambos modelos de ítems tienen un constraint que
limita el descuento a 0–100.

`number`, `issue_date` y el snapshot del emisor son nullable y quedan vacíos en
un borrador normal. La NC tampoco tiene receptor hasta emitir.
`representation_file` es un OneToOne opcional y protegido a `documents.File`,
no editable por la API ni incluido en el serializer general del comprobante.
La metadata se obtiene por el endpoint de representación.

Las relaciones fiscales y de ítems usan eliminación en cascada, excepto las
referencias protegidas a la factura desde `CreditNoteInvoice` y a `File` desde
el comprobante. Esto describe el modelo: la API no ofrece eliminación de
perfiles, puntos de venta ni comprobantes.

## Enums y estados

| Enum | Valores implementados |
| --- | --- |
| `InvoiceType` | `1` Factura A, `6` Factura B, `11` Factura C. |
| `CreditNoteType` | `3` NC A, `8` NC B, `13` NC C; homólogas de A/B/C respectivamente. |
| `InvoiceConcept` | `1` productos, `2` servicios, `3` productos y servicios. |
| `DocumentType` | `80` CUIT, `86` CUIL, `87` CDI, `96` DNI. |
| `VATCondition` | `1` responsable inscripto, `4` exento, `5` consumidor final, `6` monotributo, `13` monotributo social, `15` no alcanzado, `16` trabajador independiente promovido. |
| `VATRate` | Código `3`: 0%; `9`: 2,5%; `8`: 5%; `4`: 10,5%; `5`: 21%; `6`: 27%. El código no es el porcentaje. |
| `TaxTreatment` | `taxed`, `exempt`, `untaxed`, `not_discriminated`. |
| `TaxType` | Únicamente `vat`. |

```text
Factura: draft → issued → cancelled (cuando NC emitidas acreditan todo el total)
NC:      draft → issued
```

La API permite editar la cabecera de una factura sólo en `draft`. Los ítems de
factura y los ítems/asociaciones de NC sólo admiten modificaciones mientras el
comprobante padre está en `draft`. Una NC no tiene endpoint de edición de
cabecera, ni siquiera en borrador. Estas restricciones corresponden a views y
services; los modelos no incorporan una protección general contra escrituras
directas por ORM.

## Estructura actual

`models/` y `enums/` definen los datos anteriores. `serializers/` y `views/`
agrupan contratos y operaciones por recurso; `urls.py` define rutas explícitas.
Los services concentran las responsabilidades que requieren lógica propia:

- `rules.py`: reglas de ítems, conceptos, tipos y discriminación de IVA.
- `calculations.py`: importes y agrupación de IVA, sin acceso a base de datos.
- `numbering.py`: numeración interna de puntos de venta y comprobantes.
- `issuing.py`: emisión transaccional de facturas y NC.
- `representation.py`: PDF y asociación con Cloud, independiente de la emisión.

## Endpoints actuales

Base de todas las rutas de la tabla:
`/api/billing/companies/<uuid:company_id>/`.
Los IDs de recursos y padres anidados son enteros.

| Ruta relativa | Métodos | Resultado |
| --- | --- | --- |
| `fiscal-profile/` | GET, POST, PUT, PATCH | Consultar, crear o actualizar el único perfil fiscal. |
| `points-of-sale/` | GET, POST | Listar o crear un punto con número automático. |
| `points-of-sale/<id>/` | GET | Consultar un punto. |
| `points-of-sale/<id>/activate/` | POST | Activar; devuelve el punto actualizado. |
| `points-of-sale/<id>/deactivate/` | POST | Desactivar; devuelve el punto actualizado. |
| `invoices/` | GET, POST | Listar con filtros o crear un borrador. |
| `invoices/<id>/` | GET, PUT, PATCH | Consultar o editar la cabecera en borrador. |
| `invoices/<id>/issue/` | POST | Emitir y devolver la factura completa. |
| `invoices/<invoice_id>/items/` | GET, POST | Listar o agregar ítems. |
| `invoices/<invoice_id>/items/<id>/` | GET, PUT, PATCH, DELETE | Consultar, editar o eliminar un ítem. |
| `credit-notes/` | GET, POST | Listar o crear un borrador de NC. |
| `credit-notes/<id>/` | GET | Consultar una NC. |
| `credit-notes/<id>/issue/` | POST | Emitir y devolver la NC completa. |
| `credit-notes/<credit_note_id>/invoices/` | GET, POST | Listar asociaciones o agregar un lote de facturas. |
| `credit-notes/<credit_note_id>/invoices/<id>/` | DELETE | Eliminar una asociación y sus ítems; `<id>` identifica `CreditNoteInvoice`, no la factura. |
| `credit-notes/<credit_note_id>/items/` | GET, POST | Listar o agregar ítems de la NC. |
| `credit-notes/<credit_note_id>/items/<id>/` | GET, PUT, PATCH, DELETE | Consultar, editar o eliminar un ítem. |
| `invoices/<id>/representation/` | GET, POST | Consultar, generar o reutilizar el PDF. |
| `credit-notes/<id>/representation/` | GET, POST | Mismo flujo para NC. |

Los listados son arrays JSON sin paginación. Facturas y NC se ordenan por
`-created_at`, luego `-id`; los ítems de NC, por `id`. Los demás listados no
declaran orden explícito. Una colección sin registros devuelve `200` y `[]`.
Las altas devuelven `201`; consultas, actualizaciones, activación y emisión,
`200`; las eliminaciones disponibles, `204` sin cuerpo. La representación tiene
sus estados específicos descritos en el documento enlazado más abajo.

### Autenticación y acceso

Todos los endpoints exigen `Authorization: Bearer <access_token>` mediante
`SupabaseBearerAuthentication` y `IsAuthenticated`. Se exige `CompanyMember`
para la Company de la URL, sin distinguir entre `owner` y `member` ni conceder
excepciones por ser administrador global. Sin membresía devuelve `403`, también
si no existe la Company solicitada. Los recursos se acotan al perfil autorizado:
un ID ajeno o inexistente en una URL de detalle devuelve `404`.

Un punto de venta enviado en el body se restringe al perfil fiscal autorizado;
uno ajeno e inexistente producen el mismo error de serializer (`400`). Las
facturas y asociaciones enviadas al crear recursos de NC se restringen de la
misma manera a su Company o NC padre.

El acceso de Billing no exige `Company.is_active`, tampoco la emisión. Cloud sí
exige Company activa para almacenar una representación nueva; permite consultar
y reutilizar una ya existente. La emisión exige un punto de venta activo.

### Perfil fiscal y puntos de venta

El perfil acepta `vat_condition` obligatorio, `gross_income` opcional y
`business_start_date` opcional/nullable. `company` y timestamps son de sólo
lectura. POST rechaza un segundo perfil con `400`; GET/PUT/PATCH devuelven `404`
si un miembro consulta una Company sin perfil. PUT exige `vat_condition`;
PATCH permite cambios parciales. No se editan razón social, CUIT ni domicilio
de Company a través de este recurso.

Crear un punto no necesita payload: la view asigna el siguiente número del
perfil y lo crea activo, ignorando los campos enviados. La asignación bloquea
el perfil fiscal y comienza en 1. Su respuesta contiene `id`, `fiscal_profile`,
`number` como cadena (`"00001"`), `is_active`, `created_at`, `updated_at`.
No hay edición genérica ni DELETE; la activación/desactivación usa POST sin
payload. Consultar o crear puntos y comprobantes requiere que exista el perfil
fiscal (`404` si falta).

### Facturas: entrada y salida

POST y PUT aceptan como campos obligatorios `point_of_sale`, `invoice_type`,
`concept` y los cinco campos `receiver_*`. `service_date_from`,
`service_date_to` y `due_date` son opcionales/nullable. PATCH admite cambios
parciales. Ejemplo de creación de una factura B:

```json
{
  "point_of_sale": 1,
  "invoice_type": 6,
  "concept": 1,
  "receiver_name": "Cliente Ejemplo",
  "receiver_vat_condition": 5,
  "receiver_document_type": 96,
  "receiver_document_number": "12345678",
  "receiver_address": "Av. Ejemplo 123"
}
```

La respuesta incluye esos campos y las fechas opcionales, `id`, `status`,
`number`, `issue_date`, los cinco totales, los seis campos `issuer_*` y
timestamps. También incluye `point_of_sale_number`, `formatted_number`,
`invoice_type_display`, `concept_display`, `items` y `taxes`. La representación
del número es `00001-00000001`; `formatted_number` es `null` en borrador.

Los campos de estado, numeración, emisión, totales, snapshot, displays, ítems y
tributos son de sólo lectura y se ignoran como entrada de cabecera. No hay
escritura anidada de ítems ni endpoint para editar tributos. Los borradores
conservan totales cero: editar ítems no recalcula importes persistidos.

El listado de facturas admite filtros combinables:

| Parámetro | Comportamiento |
| --- | --- |
| `status` | Coincidencia exacta: `draft`, `issued`, `cancelled`. |
| `invoice_type` | Código de tipo `1`, `6` u `11`. |
| `point_of_sale` | ID entero del punto, no su número fiscal. Un ID ajeno no amplía el alcance de la consulta. |
| `issue_date_from`, `issue_date_to` | Límites inclusivos de fecha de emisión ISO `YYYY-MM-DD`; los borradores sin fecha no coinciden. |
| `receiver` | Coincidencia parcial sin distinguir mayúsculas en nombre o número de documento. |
| `number` | Correlativo de 1–8 dígitos o punto de 1–5 dígitos y correlativo separados por guion, por ejemplo `15` o `00001-00000015`. |

Un filtro con valor inválido devuelve `400`. No se valida el orden de los
límites de fecha. El listado de NC no implementa estos filtros.

### Ítems

El body de un ítem de factura admite `description`, `quantity`, `unit_price`,
`discount` opcional (0 por defecto), `tax_treatment` y `vat_rate` opcional.
La factura se toma de la URL; el campo `invoice` es sólo lectura. La respuesta
devuelve esos campos más `id` e `invoice`.

```json
{
  "description": "Servicio técnico",
  "quantity": "2.00",
  "unit_price": "100.00",
  "discount": "10.00",
  "tax_treatment": "taxed",
  "vat_rate": 5
}
```

Los serializers validan tipos, precisión, obligatoriedad y enums. La coherencia
fiscal, cantidad positiva y precio no negativo se comprueban al emitir, no en
el CRUD de borradores. Por ejemplo, el CRUD acepta `not_discriminated` con una
alícuota válida, pero la emisión rechaza esa combinación. El constraint de
descuento también se aplica en la base de datos.

Los ítems de NC usan el mismo contrato, sustituyendo `invoice` por
`credit_note_invoice`, obligatorio y escribible: identifica una asociación de
esa NC. Se pueden reasignar a otra asociación de la misma NC mientras esté en
borrador. Los ítems se consultan por su endpoint; no se incluyen anidados en
`CreditNoteSerializer`.

### Notas de crédito y asociaciones

La creación de NC sólo acepta `point_of_sale` y `credit_note_type`. Crea un
borrador vacío. La respuesta incluye `id`, esos dos campos, `status`, `number`,
`issue_date`, los campos de receptor, totales, snapshot del emisor y timestamps,
además de `credit_note_invoices`. No incluye `formatted_number`, displays,
`items` ni `taxes` del serializer de factura.

POST a `.../credit-notes/<id>/invoices/` recibe `{"invoices": [1, 2]}`:
lista obligatoria no vacía. Agrega asociaciones de forma acumulativa y atómica;
si falla una, no agrega ninguna. Devuelve `201` y un array de las nuevas
asociaciones, cada una con `id`, `credit_note`, `invoice` y `total` (inicialmente
`"0.00"`). GET lista todas; DELETE elimina una y sus ítems en cascada.

Al asociar se exigen facturas `issued`, de la misma Company, del tipo homólogo
de la NC y sin duplicados, incluyendo asociaciones anteriores. Deben compartir
tipo y número de documento del receptor; no se comparan su nombre, domicilio
ni condición IVA. No se exige el mismo punto de venta entre facturas y NC.

## Reglas y flujo de emisión

`POST .../issue/` no necesita body. El número y la fecha los fija el backend.
Repetir la emisión devuelve `400`; no es una operación idempotente.

### Factura

`issue_invoice()` bloquea la factura y ejecuta dentro de una transacción:

1. Exige `draft`, punto activo y emisor con razón social, CUIT válido localmente,
   calle y ciudad. Número de calle, provincia, ingresos brutos e inicio de
   actividad no son requisitos para emitir.
2. Exige al menos un ítem; cantidad `> 0`, precio `>= 0`, descuento entre 0 y 100.
   `taxed` requiere alícuota válida; los otros tratamientos exigen que esté
   ausente. Factura C no permite ítems `taxed`.
3. Valida nombre del receptor no vacío; CUIT/CUIL mediante el validador local de
   Company y CDI/DNI mediante caracteres numéricos. No consulta padrones.
4. Valida tipo según IVA del emisor y receptor: un responsable inscripto emite A
   a inscriptos o a las tres variantes de monotributo, B al resto. Emisores
   exentos o de esas variantes de monotributo sólo emiten C. Las demás
   combinaciones se rechazan.
5. Servicios y productos/servicios requieren ambas fechas de servicio, con
   inicio no posterior al fin. Productos no impone esa regla. `due_date` es
   opcional; si existe no puede preceder al día de emisión.
6. Calcula importes, asigna correlativo por punto/tipo, fija `timezone.localdate()`,
   copia el snapshot del emisor, guarda totales y `issued`, y crea `InvoiceTax`
   por alícuota gravada. Un fallo revierte toda la emisión, incluido el correlativo.

El domicilio histórico concatena calle/número, ciudad y provincia, omite
componentes vacíos y se trunca a 255 caracteres. Cambiar Company o FiscalProfile
posteriormente no actualiza los snapshots existentes.

### Nota de crédito

`issue_credit_note()` bloquea la NC y sus facturas por PK. Exige borrador, punto
activo, emisor completo, al menos una asociación, facturas todavía `issued` y
al menos un ítem por asociación. Aplica las mismas reglas de ítems y prohíbe IVA
discriminado en NC C. Las reglas de homología y receptor se verifican al asociar;
la emisión no vuelve a ejecutar esa validación ni la matriz fiscal de factura.

Calcula los totales de cada asociación y los generales. Cada importe acreditado
debe ser positivo y no superar `invoice.total` menos lo ya acreditado por NC
`issued`. Las NC en borrador no consumen saldo. El control es por importe
total de factura, sin comparación con ítems o cantidades de la factura original.

Asigna secuencia por punto y tipo de NC (independiente de facturas), fecha del
día, snapshot actual del emisor y receptor copiado de la primera asociación
ordenada por PK. No genera filas `InvoiceTax` para NC. Una factura parcialmente
acreditada sigue `issued`; al acreditarse exactamente todo su total pasa a
`cancelled`. No hay endpoint de cancelación directa ni reversión de NC.
Si algo falla se revierten NC, asociaciones, estados de facturas y numeración.

Las mutaciones de ítems y asociaciones toman el bloqueo del comprobante padre
que usa la emisión. La numeración de puntos bloquea el perfil y la de
comprobantes bloquea su secuencia. No se consulta numeración externa.

### Cálculos y precisión

Se usa `Decimal` y redondeo a centavos `ROUND_HALF_UP`: primero subtotal
(`quantity × unit_price`), luego descuento porcentual; su diferencia es el neto.
El IVA se calcula y redondea por ítem sobre el neto. Los totales suman esos
importes ya calculados: `taxed` integra `net_taxed`, `exempt` integra
`net_exempt`, y `untaxed`/`not_discriminated` integran `net_untaxed`.
`total` suma los tres netos más IVA; no hay cálculo inverso de IVA incluido.

En factura, el detalle de IVA agrupa base e importe por alícuota gravada,
incluyendo 0%, y se genera ordenado por porcentaje. Los tributos exponen `id`,
`tax_type`, `vat_rate`, `base_amount`, `amount`. No hay otros tributos
implementados. Los decimales se serializan como cadenas con dos decimales;
las fechas usan formato ISO.

## Representaciones e integraciones

El contrato completo de generación, consulta, descarga, permisos de Cloud,
reintentos y compensación está centralizado en
[BILLING_REPRESENTATION.md](BILLING_REPRESENTATION.md).
La emisión no genera el PDF ni llama a Storage. ReportLab genera el archivo
cuando se solicita; Cloud administra validación, metadata, bucket privado y
descarga mediante URL firmada.

Dependencias comprobadas:

- **Company:** propiedad y membresía, datos del emisor y validador local de CUIT.
  Véase [COMPANY.md](COMPANY.md).
- **Users/Supabase Auth:** autenticación Bearer y perfil local activo.
  Véase [USERS.md](USERS.md).
- **Cloud/Supabase Storage:** almacenamiento y descarga de representaciones,
  independiente de la emisión. Véase [CLOUD.md](CLOUD.md).
- **Accounting:** no hay imports ni llamadas de Billing a sus services o modelos;
  emitir una factura o NC no crea, publica ni revierte asientos. El origen
  `INVOICE` disponible en Accounting no constituye una integración implementada.
- **ARCA:** no hay integración operativa en el código actual. Los estados
  internos, numeración y PDF no representan autorización fiscal externa.

## Errores

Los códigos compartidos están en [ERROR_CODES.md](../ERROR_CODES.md). Billing
define únicamente `NEX-BIL-001`, para errores conocidos de generación o
asociación de la representación (`500`); Storage usa `NEX-DOC-003` (`502`).
Sus condiciones y reintentos se detallan en el documento de representaciones.
No hay códigos `NEX-BIL-*` específicos para emisión ni validación fiscal.

Las validaciones de serializer y las `DjangoValidationError` capturadas por las
views de emisión devuelven `400` en el formato estándar de DRF, con listas de
mensajes por campo o `non_field_errors`, por ejemplo:

```json
{"items": ["El comprobante debe tener al menos un ítem."]}
```

La autenticación ausente devuelve `401` con `detail` nativo; Bearer mal formado
o inválido puede devolver `NEX-USR-010`. Los errores del perfil local conservan
los códigos y estados de Users. La falta de membresía devuelve `403` con
`detail`; un recurso fuera del alcance autorizado o perfil fiscal faltante,
`404`; métodos no disponibles, `405`. No hay traducción general de constraints
o excepciones inesperadas a errores funcionales de emisión.

## Verificación existente

Los tests de `apps/billing/tests/` documentan los escenarios implementados:

| Archivo | Alcance |
| --- | --- |
| `test_fiscal_profile.py` | Unicidad, campos opcionales, CRUD permitido, enums y acceso por Company. |
| `test_point_of_sale.py`, `test_invoice_sequence.py` | Numeración, independencia por perfil/punto/tipo, activación y aislamiento. |
| `test_invoice.py`, `test_invoice_item.py` | Borradores, campos de sólo lectura, decimales, CRUD de ítems y aislamiento de relaciones. |
| `test_rules.py`, `test_calculations.py` | Tipos fiscales, fechas, IVA, descuentos, redondeo y agrupación de tributos. |
| `test_invoice_issue.py` | Emisión, snapshots, numeración y rollback, validaciones, filtros, contrato de consulta e inmutabilidad por API. |
| `test_credit_note.py` | Asociaciones atómicas, receptor, ítems, emisión, saldo disponible, acreditación parcial/total y restricciones. |
| `test_representation.py` | PDF, reutilización y concurrencia, permisos, descarga, errores, compensación y reintentos con Storage simulado. |

Esta documentación se contrastó mediante lectura de código y tests; esa revisión
no implica una ejecución de las pruebas ni una verificación con ARCA o un bucket
real.
