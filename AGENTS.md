# Instrucciones para agentes de NexusBack

## Fuente de verdad y arquitectura actual

- El código y la documentación existentes son la fuente principal de las convenciones. Estas instrucciones las complementan; no autorizan a rediseñar módulos para ajustarlos a una arquitectura "ideal".
- NexusBack es un monolito modular Django/DRF: `config/` concentra la configuración y las rutas agregadoras; cada dominio vive en `apps/<dominio>/` y conserva sus migraciones y su API.
- Las rutas públicas están bajo `/api/` y no usan versionado. Cada módulo debe conservar el patrón de routing observado en módulos equivalentes; no reemplaces routers DRF por rutas explícitas ni viceversa salvo que la tarea o una necesidad concreta lo justifique.
- Models, serializers, views/viewsets y ORM se usan según la necesidad del módulo. `services`, `selectors`, `permissions` y código compartido no son capas obligatorias: créalos sólo cuando una responsabilidad real lo justifique.
- Antes de introducir un patrón, verificá cómo resuelve el mismo problema el proyecto y el módulo afectados.

## Alcance de los cambios

- Preferí el cambio mínimo, directamente relacionado con la tarea. No modifiques código fuera de alcance ni hagas refactors laterales por iniciativa propia.
- Si detectás deuda técnica fuera de alcance, informala; no la corrijas automáticamente.
- No agregues capas, abstracciones, DTOs, services, repositories, helpers, interfaces ni dependencias nuevas si el patrón existente resuelve el problema.

## Contratos y validación

- No cambies payloads, responses, nombres o estructuras existentes sin revisar antes los consumidores relevantes. Mantené compatibilidad salvo que la tarea pida explícitamente romperla.
- Diferenciá los campos opcionales de los garantizados por contrato. Las validaciones deben vivir en la capa correspondiente y no duplicarse sin necesidad.
- Evitá condicionales o chequeos `null`/`undefined` defensivos cuando el contrato ya garantiza el dato. Ante incertidumbre, revisá primero su origen y contrato.

## Antes de modificar

- Leé los archivos relacionados, buscá implementaciones equivalentes e identificá dependencias y consumidores relevantes.
- Mantené las convenciones del módulo afectado.
- Para crear o estructurar un módulo nuevo del backend, usá `.agents/skills/backend-module/SKILL.md`.
- Para crear, modificar, corregir o revisar un endpoint HTTP, usá `.agents/skills/backend-endpoint/SKILL.md`.
