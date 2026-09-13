---
name: backend-code
description: Crear o modificar funciones, métodos y lógica dentro de módulos existentes de NexusBack, incluidos correcciones, refactors y extensiones, manteniendo una implementación simple y consistente. Complementa las skills especializadas de módulos y endpoints.
---

# Código existente de NexusBack

Aplicá primero las reglas generales de `AGENTS.md`. Esta skill define el criterio transversal de implementación; si la tarea crea un módulo o afecta un endpoint HTTP, aplicá además la skill especializada correspondiente.

## Antes de implementar

1. Delimitá el comportamiento solicitado y revisá los archivos, contratos y consumidores relevantes.
2. Buscá cómo resolvió el proyecto un caso equivalente antes de crear funciones, helpers, servicios, clases o abstracciones. Si existe una solución reutilizable, usala; si existe un patrón equivalente, seguí ese enfoque en lugar de introducir una alternativa.
3. Identificá qué responsabilidades ya cubren Django, DRF, el ORM, serializers, modelos, permissions, authentication, validators, transactions, constraints o una etapa anterior del flujo. No las reimplementes ni dupliques sus validaciones.

Preferí las APIs públicas y convencionales del framework antes que apoyarte en
comportamientos internos o detalles de implementación.

## Criterio de implementación

- Priorizá, en este orden: correcto, simple, consistente y mantenible.
- Implementá el alcance actual de forma directa. Evitá ramas inalcanzables, defensivas para escenarios hipotéticos, wrappers sin comportamiento, variables intermedias innecesarias y preparación para requisitos futuros.
- Usá el ORM cuando exprese la operación con claridad. Evitá SQL directo, filtrado manual de datos que puede resolver la base, consultas duplicadas y optimizaciones prematuras.
- Asigná cada validación a una única capa responsable. Agregala sólo si responde a un requisito funcional, contrato de entrada, regla de negocio, seguridad o límite real del sistema.
- Capturá excepciones sólo cuando haya una acción concreta: transformarlas al contrato esperado, manejar un caso conocido, agregar contexto útil o realizar compensación. No captures `Exception` para ocultar o relanzar el mismo error.
- Mantené nombres breves, claros y coherentes con el dominio y el vocabulario existente. Usá comentarios sólo para explicar decisiones o restricciones no evidentes.

## Reutilización y extracción

Usá estos criterios sin buscar reducir la cantidad de funciones a cualquier costo:

- mismo problema: reutilizá;
- problema equivalente: seguí el patrón existente;
- lógica repetida con responsabilidad común y reutilización real o inmediata: evaluá extraerla;
- responsabilidades distintas: mantenelas separadas;
- abstracción que ahorra pocas líneas pero agrega parámetros, flags, ramas o indirección: no la crees.
- Si una función existente resuelve un caso similar pero tiene consumidores activos,
  no amplíes ni generalices su contrato automáticamente. Verificá primero que el
  cambio mantenga su comportamiento actual y siga siendo claro para sus consumidores.
  Si reutilizarla obliga a introducir flags, parámetros opcionales o ramas ajenas a
  su responsabilidad original, mantené los casos separados.

No fragmentes una función corta y clara en helpers de un único uso salvo que representen una responsabilidad independiente o simplifiquen materialmente el flujo.

## Docstrings y versionado

Toda función o método nuevo debe incluir un docstring breve que explique su responsabilidad y cualquier comportamiento relevante no evidente, respetando el formato observado en el módulo e incluyendo `@version 1.0`.

Cuando cambie la lógica o el comportamiento de una función o método existente, revisá su docstring y actualizalo si corresponde:

- incrementá la versión menor (`1.1`, `1.2`) si cambia una condición, consulta o parte del flujo sin alterar sustancialmente su responsabilidad o contrato;
- incrementá la versión mayor (`2.0`, `3.0`) si cambia significativamente el contrato, responsabilidad, flujo principal o interacción con otras capas;
- no cambies `@version` por formato, comentarios, nombres internos, reorganización sintáctica, imports, ni por actualizar solamente el docstring.

No conviertas el docstring en una traducción línea por línea de la implementación.

## Revisión final

Antes de cerrar:

1. Confirmá que no duplicaste una solución, validación ni responsabilidad ya cubierta por el proyecto o el framework.
2. Simplificá helpers, ramas, consultas, excepciones o abstracciones que no aporten comportamiento claro.
3. Eliminá imports, variables, código muerto, bloques comentados y redundancias generadas por el cambio.
4. Verificá docstrings y versiones de todas las funciones o métodos creados o cuyo comportamiento cambió.
5. Confirmá que sólo modificaste los archivos necesarios y ejecutá las validaciones o tests razonables para el cambio.

Si detectás deuda técnica ajena al alcance, informala al finalizar sin corregirla automáticamente.
