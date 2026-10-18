---
name: nexusback-tests
description: Ejecutar y mantener los tests Django de NexusBack al revisar pruebas o implementar cambios funcionales del backend.
---

# Tests de NexusBack

Usá Docker Compose (`compose.test.yaml`) y el runner nativo de Django. El servicio `tests` comparte la imagen de NexusBack, espera a `test-db` y ejecuta con `--settings=config.test_settings`; este settings ignora `.env` y sólo apunta al servicio PostgreSQL de pruebas. No uses `config.settings`, SQLite ni servicios productivos para afirmar que la suite pasó.

## Selección y ejecución

1. Identificá el comportamiento afectado y buscá primero su archivo en `apps/company/tests/` (creación, búsqueda, permisos, actualización y membresías), `apps/cloud/files/tests/` (creación, descarga, listado, metadata, cuotas y permisos), `apps/cloud/excel/tests/test_sheets.py` o `apps/accounting/tests/`. Elegí el alcance más pequeño que compruebe el cambio.
2. Ejecutá con `docker compose -f compose.test.yaml run --build --rm tests python manage.py test <etiquetas> --settings=config.test_settings --noinput`. Una etiqueta puede señalar un método (`apps.company.tests.test_create.CompanyCreateTests.test_create_individual_without_tax_info`), una clase (sin el método), un archivo (`apps.company.tests.test_create`) o un módulo (`apps.company`). Django admite varias etiquetas para módulos relacionados.
3. Al finalizar un cambio funcional importante, ejecutá el módulo completo. Ejecutá `docker compose -f compose.test.yaml run --build --rm tests` cuando se solicite la suite o antes de una integración. Al terminar, `docker compose -f compose.test.yaml down -v` retira los servicios y datos efímeros de pruebas.
4. Si Docker, las dependencias o `test-db` fallan, informá el bloqueo. No uses `.venv`, SQLite, servicios productivos ni stubs temporales como alternativa automática; no presentes el descubrimiento como ejecución.

## Calidad al implementar

Identificá los comportamientos modificados y revisá su cobertura. Cuando la solicitud incluya implementación funcional y permita cambiar pruebas, agregá o actualizá sólo los casos necesarios para resultados, validaciones y seguridad relevantes; incluí autorización cuando intervengan usuarios o Companies. Agrupá tests nuevos por funcionalidad con nombres claros y convenciones Django/DRF; reutilizá fixtures y helpers si reducen duplicación real. Evitá detalles internos innecesarios, tests redundantes y cobertura artificial. Conservá los escenarios existentes y no cambies tests para ocultar una implementación incorrecta. En una solicitud sólo de ejecución o revisión, no modifiques código ni tests sin autorización explícita.

## Informe

Indicá alcance y comando, tests descubiertos y ejecutados cuando pueda determinarse, exitosos, fallidos, errores y omitidos. Separá fallos funcionales de errores de importación, configuración o conexión. Señalá funcionalidades sin verificar y posibles regresiones; si la ejecución se detuvo antes de correr casos, decilo expresamente.
