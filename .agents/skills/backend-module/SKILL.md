---
name: backend-module
description: Crear, iniciar, estructurar o implementar un módulo, app o dominio nuevo dentro de NexusBack sin introducir arquitectura o convenciones ajenas al proyecto.
---

# Módulos de NexusBack

1. Leé por completo la tarea y separá alcance, operaciones, datos, relaciones y lo explícitamente fuera de alcance.
2. Buscá uno o más módulos comparables. Identificá en ellos la ubicación bajo `apps/`, el registro de la app, models, API, rutas, agregación global, migraciones y sólo los archivos que realmente usen.
3. Creá únicamente la estructura requerida. No agregues por defecto `services`, `selectors`, `repositories`, `permissions`, `validators`, `helpers`, `utils`, DTOs, interfaces, factories ni signals.
4. Conservá nombres, estructura, estilo y patrón de routing de los equivalentes. Para cada endpoint, aplicá también `.agents/skills/backend-endpoint/SKILL.md`.
5. Mantené datos y lógica en su dominio propietario. Reutilizá modelos o conceptos existentes sólo cuando corresponda y, ante una dependencia, revisá primero cómo el proyecto modela esa relación.
6. No crees relaciones, campos, estados, abstracciones, valores alternativos ni condicionales defensivos para necesidades futuras o inciertas: verificá primero el contrato y el modelo.
7. Generá las migraciones necesarias según el procedimiento del proyecto, sin modificar migraciones históricas ni ejecutar operaciones destructivas.
8. Modificá otros módulos o configuración sólo cuando sea estrictamente necesario para integrar el dominio, como registrar la app, agregar rutas o crear una relación requerida. No aproveches esa integración para refactorizar infraestructura.

Si no hay una convención uniforme, elegí la solución mínima compatible con los patrones más cercanos, sin convertir una preferencia personal en regla global, e informá la decisión. Si la tarea y el código no definen una decisión funcional, implementá sólo lo mínimo requerido y registrá la incertidumbre para revisión.

Al finalizar, informá la estructura y archivos creados o modificados, el patrón de referencia, endpoints, modelos, relaciones y migraciones agregados, contratos y validaciones relevantes, decisiones interpretadas y deuda o mejoras dejadas fuera de alcance.
