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
| `NEX-USR-001` | La identidad autenticada por Supabase no tiene un perfil local válido en NexusBack. | `403 Forbidden` | `No fue posible autorizar la operación.` |
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
| `NEX-DOC-001` | Los datos de entrada enviados al módulo `documents` no superan la validación. | `400 Bad Request` | `Los datos enviados no son válidos.` |
| `NEX-DOC-002` | El documento solicitado no existe o no está disponible dentro de la Company indicada. | `404 Not Found` | `Documento no encontrado.` |
| `NEX-PERM-001` | El usuario autenticado no posee autorización suficiente para la operación. | `403 Forbidden` | `No fue posible autorizar la operación.` |
| `NEX-PERM-002` | La operación requiere `is_system_admin = True`, pero el usuario no es administrador global. | `403 Forbidden` | `No fue posible autorizar la operación.` |

El registro y el inicio de sesión mediante Supabase Auth están implementados,
y los errores conocidos de Auth se traducen a códigos HTTP de NexusBack. Los
endpoints protegidos de `users` validan JWT Bearer contra Supabase Auth.
