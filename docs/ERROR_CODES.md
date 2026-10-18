# Códigos de error internos

NexusBack usa códigos internos con el formato `NEX-<AREA>-<NUMERO>` para
identificar casos operativos sin exponer su causa técnica en las respuestas
públicas. El cliente recibe sólo un mensaje deliberadamente genérico.

El catálogo crece a demanda: no se reservan ni se inventan códigos sin un caso
real de implementación o defensa de acceso.

## Convención de logging

Cuando exista el contexto que origine un error, se utiliza el sistema estándar
`logging` de Python/Django con un mensaje descriptivo, por ejemplo:

```text
[NEX-USR-002] User profile is inactive.
```

Puede incluirse un identificador útil para diagnóstico, como el UUID del
usuario. Nunca se registran access tokens, refresh tokens, contraseñas,
secretos, Supabase service keys ni credenciales completas.

## Códigos actuales

| Código | Caso interno | HTTP | Mensaje público |
| --- | --- | --- | --- |
| `NEX-AUTH-001` | Autenticación ausente o inválida. No distingue públicamente entre token inexistente, inválido o vencido. | `401 Unauthorized` | `No fue posible autenticar la solicitud.` |
| `NEX-USR-001` | La identidad autenticada no puede vincularse a un perfil local existente. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-USR-002` | El perfil local existe pero `is_active = False`. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-USR-003` | Los datos de entrada enviados al módulo `users` no superan la validación. | `400 Bad Request` | `Los datos enviados no son válidos.` |
| `NEX-USR-004` | Se solicitó un usuario que no existe. | `404 Not Found` | `Usuario no encontrado.` |
| `NEX-USR-005` | Supabase Auth no creó una cuenta durante el registro. | `502 Bad Gateway` | `No fue posible crear la cuenta.` |
| `NEX-USR-006` | La cuenta fue creada en Supabase Auth, pero no se pudo crear su perfil local. | `500 Internal Server Error` | `No fue posible completar el registro.` |
| `NEX-USR-007` | Supabase Auth alcanzó temporalmente un límite de solicitudes de autenticación. | `429 Too Many Requests` | `Se alcanzó temporalmente el límite de solicitudes. Intente nuevamente más tarde.` |
| `NEX-USR-008` | Las credenciales de acceso no son válidas. | `401 Unauthorized` | `Email o contraseña incorrectos.` |
| `NEX-USR-009` | Supabase Auth no pudo iniciar sesión. | `502 Bad Gateway` | `No fue posible iniciar sesión.` |
| `NEX-USR-010` | El header Bearer está ausente, mal formado, vencido o no puede validarse ante Supabase Auth. | `401 Unauthorized` | `No fue posible autenticar la solicitud.` |
| `NEX-USR-011` | El usuario autenticado no tiene permisos para la operación solicitada, incluidos los intentos de auto-desactivación o auto-despromoción. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-USR-012` | Error interno al validar el perfil del usuario autenticado. | `500 Internal Server Error` | `Error interno al validar el perfil del usuario autenticado.` |
| `NEX-USR-013` | Supabase Auth no pudo cerrar la sesión solicitada. | `502 Bad Gateway` | `No fue posible cerrar la sesión.` |
| `NEX-USR-014` | Supabase Auth no pudo actualizar la contraseña del usuario autenticado. | `502 Bad Gateway` | `No se pudo actualizar la contraseña.` |
| `NEX-DOC-001` | Los datos de entrada enviados al módulo `cloud/files` no superan la validación. | `400 Bad Request` | `Los datos enviados no son válidos.` |
| `NEX-DOC-002` | El documento solicitado no existe o no está disponible dentro de la Company indicada. | `404 Not Found` | `Documento no encontrado.` |
| `NEX-DOC-003` | Supabase Storage no pudo almacenar un documento. | `502 Bad Gateway` | `No fue posible almacenar el documento.` |
| `NEX-DOC-004` | Supabase Storage no pudo generar la URL firmada de descarga. | `502 Bad Gateway` | `No fue posible preparar la descarga del documento.` |
| `NEX-DOC-005` | Supabase Storage no pudo devolver el contenido del archivo para su lectura. | `502 Bad Gateway` | `No fue posible leer el archivo almacenado.` |
| `NEX-DOC-006` | El contenido asociado a un archivo `.xlsx` no es un libro XLSX válido. | `400 Bad Request` | `El archivo XLSX no es válido.` |
| `NEX-DOC-007` | La hoja solicitada no existe en el archivo XLSX. | `404 Not Found` | `Hoja no encontrada.` |
| `NEX-PERM-001` | El usuario autenticado no posee autorización suficiente para la operación. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-PERM-002` | La operación requiere `is_system_admin = True`, pero el usuario no es administrador global. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-COM-001` | Los datos de entrada enviados al módulo `company` no superan la validación, incluido un CUIT estructuralmente inválido o duplicado. | `400 Bad Request` | `Los datos enviados no son válidos.` |

El registro y el inicio de sesión mediante Supabase Auth están implementados,
y los errores conocidos de Auth se traducen a códigos HTTP de NexusBack. Los
endpoints protegidos de `users` validan JWT Bearer contra Supabase Auth.

## Accounting

Los códigos `NEX-ACC-*` identifican únicamente los errores funcionales propios
de Accounting. Sus detalles se conservan en este catálogo; la respuesta HTTP
pública incluye sólo el campo `code`.

| Código | Caso interno | HTTP | Descripción |
| --- | --- | --- | --- |
| `NEX-ACC-001` | Cuenta duplicada dentro de una Company. | `400 Bad Request` | Lo genera el serializer al detectar un código ya utilizado. También identifica una colisión de la restricción de unicidad `unique_account_company_code` posterior a la validación. La respuesta pública es `{"code": "NEX-ACC-001"}`. |
| `NEX-ACC-002` | Modificación prohibida de datos históricos de una cuenta. | `400 Bad Request` | Se intenta cambiar `code`, `name` o `account_type` de una cuenta utilizada en un asiento `POSTED` o `REVERSED`. La respuesta pública es `{"code": "NEX-ACC-002"}`. |
| `NEX-ACC-003` | Publicación rechazada por reglas contables. | `400 Bad Request` | El asiento no está en `DRAFT`, tiene menos de dos movimientos, está desbalanceado o utiliza cuentas no válidas. La respuesta pública es `{"code": "NEX-ACC-003"}`. |
| `NEX-ACC-004` | Reversión rechazada por reglas contables. | `400 Bad Request` | El asiento no está en `POSTED` o falla una regla contable del flujo de reversión. La respuesta pública es `{"code": "NEX-ACC-004"}`. |

Los errores estándar de Django REST Framework que no tienen uno de estos códigos
conservan su respuesta anterior. La colisión de unicidad se reconoce por el
diagnóstico de la restricción en PostgreSQL y por el diagnóstico exacto de las
columnas únicas en SQLite; los demás `IntegrityError` se propagan normalmente.
