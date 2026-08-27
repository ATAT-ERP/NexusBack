---
name: backend-endpoint
description: Crear, modificar, corregir o revisar endpoints HTTP de NexusBack, incluidos rutas, views/viewsets, serializers, autenticación, permisos y contratos de request/response.
---

# Endpoints de NexusBack

1. Confirmá el alcance exacto y localizá el módulo y endpoint involucrados.
2. Revisá rutas, handlers, serializers, modelos y las capas que el módulo realmente use; buscá implementaciones equivalentes antes de proponer un patrón.
3. Determiná el contrato vigente de request y response, incluidos autenticación, permisos, códigos de estado, errores y campos opcionales. Si se modifica algo existente, identificá antes sus consumidores relevantes.
4. Conservá el patrón del módulo: los recursos convencionales pueden usar router y ViewSet/mixins de DRF; las operaciones especiales usan rutas y vistas explícitas cuando así lo haga el código existente. No conviertas un estilo en otro sin necesidad.
5. Reutilizá serializers y validaciones existentes cuando correspondan. Ubicá cada validación en la capa responsable y no agregues defensivas si el contrato ya garantiza el dato.
6. Implementá sólo el cambio necesario. No introduzcas arquitectura, capas, dependencias ni componentes de Django por costumbre; por ejemplo, no agregues Auth, Admin o Sessions si la tarea y el módulo no los requieren.
7. Aplicá el manejo de errores, logging y códigos internos que ya use el módulo; no expongas secretos, contraseñas ni tokens en respuestas o logs.
8. No corrijas deuda técnica ajena al alcance. Verificá el flujo principal y los casos relevantes que pueda afectar el cambio.

Al finalizar, informá los archivos modificados, el comportamiento implementado, cualquier contrato afectado, las validaciones realizadas y la deuda o riesgos detectados que se dejaron fuera del alcance.
