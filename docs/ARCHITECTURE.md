# Arquitectura de NexusBack

## 1. Objetivo

NexusBack es el backend principal de A.T.A.T. ERP. Esta base inicial contiene
la configuración técnica necesaria para desarrollar el ERP de forma
incremental y el dominio funcional base `users`; no contiene integración de
autenticación.

## 2. Tipo de arquitectura

El proyecto es un **monolito modular orientado a dominios**. Se despliega como
una única aplicación Django, mientras que cada capacidad importante del ERP se
implementa como una Django App independiente.

Esta decisión mantiene simple el despliegue y permite desarrollar por etapas,
con responsabilidades claras y módulos desacoplados. Evita introducir de forma
prematura la complejidad operativa de microservicios, arquitectura hexagonal o
capas abstractas sin una necesidad concreta.

## 3. Estructura general

```text
NexusBack/
├── config/     # Configuración global, entradas ASGI/WSGI y rutas agregadoras
├── apps/       # Contenedor de los dominios funcionales
├── docs/       # Documentación técnica y arquitectónica
├── manage.py
├── requirements.txt
└── .env.example
```

`config` no contiene lógica de negocio. `apps` agrupa el código por dominio.
`shared` no existe todavía porque no hay código transversal real: se creará sólo
cuando una implementación sea reutilizada por varios dominios. `docs` conserva
las decisiones técnicas que deben conocer las personas y los agentes que
trabajen sobre el repositorio.

## 4. Dominios

Cada funcionalidad importante será una Django App dentro de `apps/<domain>/`.
El primer dominio creado es `apps/users/`, que representa el perfil funcional
del usuario dentro del ERP. Supabase Auth es la autoridad de identidad y
autenticación: gestiona email, contraseña, recuperación de contraseña, sesiones
y futuros proveedores sociales. NexusBack no almacena contraseñas y
posteriormente validará los JWT emitidos por Supabase.

`users.User` comparte el UUID de la identidad de Supabase y contiene sólo datos
funcionales, como estado y administración global. Otros dominios podrán
relacionarse posteriormente con este perfil, por ejemplo mediante una futura
`CompanyMembership`, sin incorporar empresas ni roles empresariales a `users`.

Una app crecerá según sus responsabilidades reales. Cuando lo necesite, podrá
incluir `migrations/`, `models/`, `services/`, `selectors/`, `api/`, `urls.py`,
`permissions.py` y `tests/`. No se crean carpetas, clases o archivos vacíos
sólo para representar esta convención.

La capa `api/` agrupa las piezas HTTP del dominio, como serializers y Views o
ViewSets, cuando el tamaño del módulo justifique esa separación.

## 5. Responsabilidades

- **models**: modelos ORM, relaciones y comportamiento propio de una entidad.
- **migrations**: cambios de esquema del dominio propietario; se versionan junto
  con su app.
- **services**: operaciones y reglas de negocio que no deben quedar acopladas a
  HTTP. No se crean para operaciones triviales.
- **selectors**: consultas o lecturas de complejidad relevante.
- **serializers**: serialización, deserialización y validación con DRF.
- **views / ViewSets**: capa HTTP; deben ser pequeñas y delegar la lógica de
  negocio cuando corresponda.
- **urls**: rutas propias del dominio.
- **permissions**: permisos específicos del dominio, sólo cuando sean
  necesarios.
- **tests**: pruebas del comportamiento del dominio, mantenidas con la app.

## 6. Flujo general

Una operación protegida seguirá este flujo:

```text
Request → Authentication → User profile → Permissions → View / ViewSet → Serializer → Model → DB
```

La autenticación futura validará el JWT de Supabase antes de acceder al perfil
funcional de `users`; los permisos decidirán la autorización antes de la View.
Las respuestas públicas de autenticación y autorización no expondrán detalles
internos. Los casos internos se documentan incrementalmente en
`docs/ERROR_CODES.md` y podrán registrarse con `logging` estándar. No toda
operación debe atravesar todas las capas. Los CRUD simples pueden usar las
herramientas nativas de Django REST Framework; Services y Selectors se
introducen cuando separan una responsabilidad real.

## 7. Código compartido

Una funcionalidad permanece en su dominio mientras sólo le pertenezca a él.
`shared` se creará exclusivamente para código reutilizado por múltiples
dominios: por ejemplo, excepciones, permisos, paginación, utilidades o
contratos comunes. **shared no debe convertirse en un cajón de sastre.**

Cuando varios dominios necesiten contratos, tipos estructurales, `Protocol`,
`dataclass` o `enum` comunes, podrán ubicarse en `shared/contracts/`. Los
serializers de DRF no son contratos globales por defecto.

## 8. Dependencias entre módulos

Se evitan dependencias circulares y el acceso indiscriminado a internals de
otras apps. Las colaboraciones necesarias se expresarán mediante APIs internas
claras, Services, Selectors, contratos compartidos o mecanismos de Django, de
acuerdo con el caso concreto. Las excepciones relevantes se documentarán.

## 9. API REST

La API se organiza bajo el prefijo `/api/<domain>/`, por ejemplo
`/api/companies/`. `config/urls.py` es el agregador global;
cada dominio registrará y mantendrá sus propias rutas. Para CRUDs convencionales
se podrán usar ViewSets y routers de DRF. Para operaciones especiales se podrán
usar APIViews o rutas explícitas.

El único endpoint actual es `GET /api/health/`: un health check técnico que
no representa una funcionalidad del ERP ni consulta la base de datos.

## 10. Base de datos y migraciones

El acceso a datos se realizará mediante Django ORM. Cada dominio será dueño de
sus migraciones y las mantendrá versionadas junto a su app; no habrá una carpeta
global de migraciones del ERP.

PostgreSQL alojado en Supabase es la única base de datos soportada por
NexusBack; sus parámetros de conexión se suministran mediante variables de
entorno y su ausencia detiene el arranque explícitamente. Django y cada dominio
mantienen la responsabilidad de sus migraciones. La infraestructura de
Supabase Auth será la autoridad de autenticación, pero su integración no se
implementa todavía y no se almacenan credenciales en el repositorio.

## 11. Principios de evolución

- No crear abstracciones ni dependencias sin una necesidad real.
- No crear carpetas sólo para aparentar arquitectura.
- Mantener la lógica de negocio fuera de las Views.
- Mantener cada funcionalidad en su dominio.
- Mover código a `shared` únicamente cuando sea realmente transversal.
- Priorizar convenciones nativas de Django y Django REST Framework.
- Mantener bajo acoplamiento entre módulos.

## 12. Regla para futuros cambios

**Si una decisión futura modifica la arquitectura general de NexusBack,
`docs/ARCHITECTURE.md` debe actualizarse en el mismo cambio.** El código y la
documentación arquitectónica no deben divergir.
