# Payment Processing API

API de procesamiento de pagos para comercios: registro de transacciones sin duplicados, control
de estados con auditoría completa y conciliación automática de pagos vencidos. Desarrollada en
Python siguiendo los principios de **Clean Architecture**.

## Qué resuelve

Un comercio solicita procesar un pago a través de la API. A partir de ahí, el sistema debe
garantizar tres cosas que en un dominio financiero no son negociables:

1. **Que un pago no se duplique**, aunque el cliente reintente la misma petición o dos peticiones
   idénticas lleguen exactamente al mismo tiempo.
2. **Que el dinero sea exacto**, sin errores de redondeo por usar números flotantes.
3. **Que todo cambio quede trazado**, sabiendo quién lo hizo y por qué.

Sobre esa base, la solución permite crear comercios, registrar y consultar pagos con filtros,
cambiar su estado respetando transiciones válidas, consultar el historial de cada cambio, obtener
un resumen de movimientos por comercio y ejecutar un proceso que rechaza automáticamente los pagos
que llevan demasiado tiempo pendientes.

## Quién consume la API

No es lo mismo una persona operando el back office que otro sistema integrado, y el sistema los
distingue: cada uno se autentica de forma distinta y queda registrado de forma distinta en la
auditoría.

```mermaid
flowchart TB
    operator["Usuario interno / Operador<br/>(autentica con JWT)"]
    integrator["Comercio / Integrador<br/>(autentica con API Key)"]
    other["Otro servicio interno<br/>(reutiliza payment-db-models)"]
    system["Payment Processing API<br/>Procesa pagos, comercios,<br/>historial y conciliacion"]
    db[("PostgreSQL")]
    operator -->|"HTTPS / JWT"| system
    integrator -->|"HTTPS / API Key"| system
    system --> db
    other -.->|"comparte esquema"| db
```

El tercer actor no consume la API, sino el **esquema**: los modelos de base de datos viven en un
paquete independiente para que cualquier otro servicio pueda reutilizarlos sin duplicar código.
Esa decisión se explica más adelante, en [Migraciones](#migraciones).

## Cómo está construido

### Las capas

La aplicación se organiza en capas concéntricas: las dependencias apuntan **siempre hacia
adentro**, hacia el dominio. Cada capa conoce a la que la envuelve, nunca al revés.

```mermaid
flowchart TB
    subgraph L4["api/ — detalles de transporte (HTTP)"]
        direction TB
        api["Routers · schemas Pydantic · auth + RBAC · manejo de errores"]
        subgraph L3["infrastructure/ — detalles de I/O"]
            direction TB
            infra["Repositorios SQLAlchemy · Unit of Work · Redis · JWT · metricas"]
            subgraph L2["application/ — casos de uso"]
                direction TB
                app["PaymentService · MerchantService · AuthService · ReconciliationService"]
                subgraph L1["domain/ — nucleo de negocio"]
                    dom["Money · maquina de estados · errores · permisos"]
                end
            end
        end
    end

    api -.->|depende de| infra
    infra -.->|depende de| app
    app -.->|depende de| dom
```

La consecuencia práctica: el núcleo no sabe que existen FastAPI, PostgreSQL ni Redis, así que las
reglas de negocio se prueban sin levantar una base de datos y sobreviven a un cambio de framework.

| Capa | Responsabilidad | De qué **no** depende |
| --- | --- | --- |
| `domain/` | Reglas puras: value object `Money`, máquina de estados, errores de negocio, catálogo de permisos | De nada del framework ni de la base de datos |
| `application/` | Casos de uso que orquestan el dominio y persisten vía repositorios | De FastAPI ni de HTTP |
| `infrastructure/` | Implementaciones concretas: repositorios SQLAlchemy, Unit of Work, sesiones en Redis, JWT, métricas | — |
| `api/` | Transporte HTTP: routers, schemas Pydantic, autenticación y RBAC, manejo de errores | — |

La regla se cumple donde más importa: **`domain/` no importa nada de `infrastructure/`**. Como
decisión pragmática, `application/` recibe el `UnitOfWork` concreto en lugar de una interfaz: con
un único motor de persistencia, la inversión de dependencias completa añadiría indirección sin
beneficio real. Si mañana hubiera que soportar otro almacenamiento, ahí sí se extraería el puerto.

Esa misma separación se ve al abrir el contenedor de la API, donde cada flecha respeta la
dirección anterior:

```mermaid
flowchart TB
    subgraph api[API - app/]
        routers["api/ (routers + schemas)<br/>auth, merchants, payments"]
        deps["api/deps.py<br/>auth dual (JWT / API Key) + RBAC"]
        app["application/ (casos de uso)<br/>PaymentService, MerchantService,<br/>AuthService, ReconciliationService"]
        domain["domain/<br/>Money, maquina de estados,<br/>errores, permisos"]
        infra["infrastructure/<br/>UnitOfWork, repositorios,<br/>sesiones Redis, JWT, metricas"]
    end
    models["payment-db-models"]
    redis[("Redis")]
    pg[("PostgreSQL")]
    routers --> deps
    routers --> app
    deps --> infra
    app --> domain
    app --> infra
    infra --> models
    infra --> redis
    models --> pg
```

### Las piezas en ejecución

En tiempo de ejecución hay más de un proceso. La API atiende peticiones, pero la conciliación
corre por su cuenta en dos contenedores separados, y Redis cumple **doble propósito**: guarda las
sesiones y actúa como *broker* de Celery, evitando sumar infraestructura solo para las colas.

```mermaid
flowchart TB
    subgraph clients[Clientes]
        operator["Operador (JWT)"]
        integrator["Integrador (API Key)"]
    end
    api["API — FastAPI"]
    worker["Reconciliation Worker — Celery"]
    beat["Celery Beat"]
    redis[("Redis — sesiones + broker")]
    pg[("PostgreSQL")]
    models["payment-db-models (paquete compartido)"]
    prom["Prometheus"]
    graf["Grafana"]
    operator --> api
    integrator --> api
    api --> redis
    api --> pg
    beat --> redis
    redis --> worker
    worker --> pg
    api -. usa .-> models
    worker -. usa .-> models
    prom -->|scrape| api
    prom -->|scrape| worker
    graf --> prom
```

### Estructura del repositorio

```
libs/
  payment-db-models/     Paquete independiente: modelos SQLAlchemy + migraciones Alembic
services/
  api/                   FastAPI
    app/domain/          Entidades, Money, máquina de estados, errores, permisos
    app/application/     Casos de uso (PaymentService, AuthService, Reconciliation...)
    app/infrastructure/  UnitOfWork, repositorios, sesiones Redis, JWT, métricas
    app/api/             Routers, schemas Pydantic, dependencias (auth + RBAC), handlers
  reconciliation/        Worker Celery que reutiliza el caso de uso de conciliación
observability/           Config de Prometheus + provisioning y dashboard de Grafana
scripts/                 Seed idempotente (roles, permisos, admin, API key)
docs/postman/            Colección de Postman lista para importar
```

## Puesta en marcha

Requisitos: Docker y Docker Compose. Para desarrollo local sin Docker, Python 3.12+, PostgreSQL y
Redis.

```bash
cp .env.example .env
docker compose up --build
```

El arranque ejecuta en orden las migraciones (`migrate`) y la carga inicial de roles, permisos y
administrador (`seed`); solo cuando ambos terminan correctamente levantan la API, el worker y el
scheduler.

| Servicio | URL |
| --- | --- |
| API | http://localhost:8000 |
| Swagger / OpenAPI | http://localhost:8000/docs |
| Métricas de la API | http://localhost:8000/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (`admin` / `admin`) |

En Grafana, el dashboard **Payment Processing — Overview** queda provisionado automáticamente.

### Primeros pasos

```bash
# 1. Login como administrador (lo crea el seed)
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@payments.com","password":"admin12345"}' | jq -r .access_token)

# 2. Crear un comercio
curl -X POST localhost:8000/api/v1/merchants -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Comercio Prueba","document_number":"900123456","email":"c@example.com"}'

# 3. Registrar un pago (la cabecera Idempotency-Key es obligatoria)
curl -X POST localhost:8000/api/v1/payments -H "Authorization: Bearer $TOKEN" \
  -H 'Idempotency-Key: payment-001' -H 'Content-Type: application/json' \
  -d '{"merchant_id":"<uuid>","external_reference":"ORDER-1001","amount":150000,"currency":"COP","payment_method":"QR"}'
```

## El ciclo de vida de un pago

### 1. Registro: por qué no se duplica

Cada creación exige la cabecera `Idempotency-Key`. Si el cliente reintenta con la misma llave,
recibe **el pago original**, no uno nuevo.

El caso difícil no es el reintento secuencial, sino **dos peticiones simultáneas** con la misma
llave: ambas consultan, ambas ven que no existe y ambas intentan crear. La solución no está en la
aplicación sino en la base de datos, que es el único punto donde la concurrencia se resuelve de
verdad: hay una **restricción única** sobre `idempotency_key`. Una petición gana el `INSERT` y la
otra recibe un `IntegrityError`, hace *rollback* y devuelve el pago que acaba de crear su
competidora.

```mermaid
sequenceDiagram
    participant A as Request A
    participant B as Request B
    participant API as API
    participant DB as PostgreSQL
    Note over A,B: Misma Idempotency-Key en paralelo
    A->>API: POST /payments (Idempotency-Key: K)
    B->>API: POST /payments (Idempotency-Key: K)
    API->>DB: SELECT by idempotency_key = K (A)
    API->>DB: SELECT by idempotency_key = K (B)
    Note over DB: Ninguno existe todavia
    API->>DB: INSERT payment (A)
    DB-->>API: OK (commit A)
    API->>DB: INSERT payment (B)
    DB-->>API: IntegrityError (unique idempotency_key)
    API->>DB: rollback + SELECT by idempotency_key = K (B)
    DB-->>API: pago creado por A
    Note over API: incrementa payments_idempotency_conflicts_total
    API-->>A: 201 Created (pago P)
    API-->>B: 201 Created (mismo pago P)
```

Nótese que **no hay bloqueos explícitos**: la restricción única hace el trabajo, y el conflicto se
trata como un caso esperado en vez de como un error. La misma protección se aplica a la pareja
`(merchant_id, external_reference)`, que también es única; ahí sí, un duplicado real devuelve
`409 Conflict` porque se trata de otra operación distinta con una referencia ya usada.

Esto está verificado por una prueba que lanza **ocho peticiones concurrentes** con la misma llave
y comprueba que en la base de datos queda exactamente un pago.

### 2. Estados: qué transiciones son legales

Un pago nace en `PENDING` y solo puede avanzar. Los estados finales son terminales: un pago
aprobado no vuelve a pendiente ni pasa directamente a rechazado.

```mermaid
flowchart LR
    PENDING(["PENDING"])
    APPROVED(["APPROVED"])
    REJECTED(["REJECTED"])
    CANCELLED(["CANCELLED"])
    PENDING -->|aprobar| APPROVED
    PENDING -->|rechazar / conciliacion| REJECTED
    PENDING -->|cancelar| CANCELLED
    APPROVED -.->|no permitido| PENDING
    REJECTED -.->|no permitido| PENDING
    CANCELLED -.->|no permitido| PENDING
```

Estas reglas viven en el dominio (`domain/payment_status.py`), no en el controlador, y se validan
**antes** de tocar la base de datos. Cualquier transición ilegal devuelve `422` con el código
`INVALID_PAYMENT_STATUS`.

### 3. Trazabilidad: quién cambió qué

Cada transición escribe una fila en el historial con el estado anterior, el nuevo, el motivo, la
fecha y **el actor**. Consultando `GET /api/v1/payments/{id}/history` se ve la vida completa del
pago:

```
None    -> PENDING    by user:9f3c...    | Payment created
PENDING -> REJECTED   by service:reconciliation | Auto-rejected: pending longer than allowed window
```

El actor distingue si el cambio lo hizo una persona (`user:<uuid>`) o un sistema
(`service:<uuid>`), que es justo la diferencia establecida en [Quién consume la
API](#quién-consume-la-api).

### El dinero, en todo el recorrido

Los importes nunca tocan un `float`. Se modelan con un value object `Money` que valida que sean
mayores que cero, viajan como `Decimal` y se almacenan en `NUMERIC(18,2)`. Un `float` no puede
representar exactamente 0.1, y en un sistema financiero ese error se acumula transacción a
transacción.

## Autenticación y control de acceso

### Los dos tipos de consumidor

| | Usuario (persona) | Servicio (sistema) |
| --- | --- | --- |
| Mecanismo | JWT (`Authorization: Bearer <token>`) | API Key (`X-API-Key: <clave>`) |
| Cómo se obtiene | `POST /api/v1/auth/login` | Se aprovisiona por seed (`SERVICE_API_KEY`) |
| Vigencia | Access token corto + refresh rotativo | Estática hasta revocarla |
| Permisos | Los de sus roles en base de datos | Conjunto fijo de servicio |
| Sesión | Única por usuario, revocable al instante | Sin sesión (no aplica) |
| Queda registrado como | `user:<uuid>` | `service:<uuid>` |

Las API Keys se guardan **hasheadas**: si alguien lee la base de datos, no obtiene credenciales
utilizables.

### Permisos y roles

Los permisos son **filas en la base de datos** (tabla `permissions`), no un enum en el código, y
se evalúan en tiempo de ejecución. Eso permite crear roles nuevos sin desplegar.

| Permiso | Autoriza a |
| --- | --- |
| `merchants:create` | Crear comercios |
| `merchants:read` | Consultar comercios y su resumen |
| `payments:create` | Registrar pagos (y generar los de demo) |
| `payments:read` | Consultar y listar pagos e historial |
| `payments:transition` | Cambiar el estado de un pago |
| `roles:manage` | Administrar roles y permisos |

Un rol es un conjunto de permisos (`roles` ↔ `permissions`, relación muchos a muchos):

| Rol | Permisos | Para quién |
| --- | --- | --- |
| **ADMIN** | Todos los anteriores | Administración: crear comercios, cambiar estados, gestionar roles |
| **OPERATOR** | `merchants:read`, `payments:create`, `payments:read` | Operación diaria: registrar y consultar, **sin** poder aprobar ni rechazar |
| *(servicio)* | `merchants:read`, `payments:create`, `payments:read`, `payments:transition` | Integraciones automáticas. No es un rol en BD: es el conjunto fijo que se asigna al autenticar por API Key |

Quien se registra por `POST /api/v1/auth/register` recibe **OPERATOR** por defecto. La separación
tiene intención: un operador puede registrar pagos, pero **no aprobarlos** — eso exige
`payments:transition`, y así el registro de una transacción queda separado de su autorización.

Un permiso faltante devuelve `403 PERMISSION_DENIED`; la ausencia de credenciales,
`401 AUTHENTICATION_REQUIRED`.

### Sesión única y robo de token

Las sesiones viven en Redis bajo la clave `session:{user_id}`. Como hay **una sola clave por
usuario**, un login nuevo sobrescribe el anterior: solo existe una sesión activa a la vez.

El access token lleva dentro un identificador de sesión (`sid`) que se valida contra Redis en cada
petición. Por eso revocar una sesión surte efecto **de inmediato**, sin esperar a que expire el
token: la validación no depende solo de la firma.

Contra el robo de credenciales, el refresh token **rota en cada uso**. Si llega uno ya rotado
significa que dos partes tienen el mismo token —el legítimo y quien lo robó—, así que se destruye
la sesión completa y ambos quedan fuera:

```mermaid
sequenceDiagram
    participant U as Cliente
    participant API as API
    participant R as Redis
    U->>API: POST /auth/login (email, password)
    API->>R: SET session:{user} = {sid, hash(refresh)}
    Note over R: sobrescribe cualquier sesion previa (sesion unica)
    API-->>U: access (sid) + refresh
    U->>API: request con access token
    API->>R: GET session:{user}
    R-->>API: sid vigente coincide -> autorizado
    U->>API: POST /auth/refresh (refresh actual)
    API->>R: hash coincide -> rota (nuevo sid + refresh)
    API-->>U: nuevo access + refresh
    U->>API: POST /auth/refresh (refresh viejo, ya rotado)
    API->>R: hash NO coincide -> DEL session:{user}
    Note over R: reuso detectado = posible robo -> mata la sesion
    API-->>U: 401 SESSION_EXPIRED
```

Es preferible forzar un nuevo inicio de sesión al usuario legítimo antes que dejar viva una sesión
posiblemente comprometida.

## Conciliación automática

Un pago que se queda en `PENDING` para siempre es dinero en un limbo contable. El proceso de
conciliación rechaza automáticamente los que superan `PENDING_TIMEOUT_MINUTES` (30 por defecto).

### Quién programa y quién ejecuta

Celery separa **el reloj** del **ejecutor**, y por eso son dos contenedores distintos:

| Contenedor | Comando que ejecuta | Qué hace |
| --- | --- | --- |
| `reconciliation-beat` | `celery -A worker.celery_app beat --loglevel=info` | Es el *scheduler* (equivale a un cron). Cada `RECONCILIATION_INTERVAL_SECONDS` publica un mensaje en Redis. **No toca la base de datos** |
| `reconciliation-worker` | `celery -A worker.celery_app worker --pool=solo --loglevel=info` | Consume el mensaje y **hace el trabajo real**: consulta, actualiza estados, escribe historial y expone métricas en el puerto `9808` |

```mermaid
sequenceDiagram
    participant Beat as Celery Beat
    participant W as Worker
    participant DB as PostgreSQL
    Beat->>W: dispara reconcile_pending_payments (cada N seg)
    W->>DB: SELECT pagos PENDING con created_at < now - 30 min
    DB-->>W: lista de pagos vencidos
    loop por cada pago
        W->>DB: UPDATE status = REJECTED
        W->>DB: INSERT historial (changed_by = service:reconciliation)
    end
    W->>DB: commit
    Note over W: payments_reconciliation_processed_total += N
    W-->>Beat: retorna cantidad procesada
```

El traspaso se ve en los logs, con Redis en medio:

```
beat    | Scheduler: Sending due task reconcile-pending-payments
worker  | Task worker.tasks.reconcile_pending_payments[...] received
worker  | Reconciliation rejected 3 stale pending payments
worker  | Task ... succeeded in 0.016s: 3
```

La tarea **reutiliza el mismo caso de uso del dominio** que usaría la API, de modo que la regla de
negocio existe en un solo lugar.

### Varias instancias a la vez

Los **workers escalan horizontalmente**: se pueden correr N contenedores repartiéndose la carga.
El **scheduler debe ser único**, igual que cualquier cron: si hay tres, el job se dispara tres
veces.

Aun así, la corrección **no depende** de eso. La consulta usa `SELECT ... FOR UPDATE SKIP LOCKED`,
de modo que si varias corridas coinciden, cada transacción toma un subconjunto distinto de filas y
las demás saltan las que están bloqueadas. Cada pago se procesa **exactamente una vez**, sin
historial duplicado, aunque el disparo se duplique.

`--pool=solo` está puesto únicamente para que las métricas queden en el mismo proceso que las
expone; no es un límite de escalado. En producción se usaría el pool `prefork`.

### Ejecutarla a demanda

Para no esperar al scheduler, el mismo caso de uso se invoca como script de una sola corrida (útil
en demostraciones y como cron del sistema):

```bash
docker compose run --rm reconciliation-worker python -m worker.run_once
# -> Reconciliation rejected 3 stale pending payments
```

### Generar pagos vencidos para probarla

Esperar media hora no es práctico, así que hay un endpoint que genera pagos aleatorios **ya
vencidos**: importe y medio de pago al azar, asignados a un comercio existente elegido al azar y
con `created_at` retrocedido.

```bash
# 1. Generar 3 pagos PENDING con 45 minutos de antigüedad
curl -X POST localhost:8000/api/v1/demo/payments/random \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"count": 3, "age_minutes": 45}'

# 2. Ejecutar la conciliación sin esperar al scheduler
docker compose run --rm reconciliation-worker python -m worker.run_once
# -> Reconciliation rejected 3 stale pending payments
```

El historial resultante muestra los dos actores implicados:

```
None    -> PENDING    by service:demo            | Demo payment generated
PENDING -> REJECTED   by service:reconciliation  | Auto-rejected: pending longer than allowed window
```

Está detrás de `DEMO_ENDPOINTS_ENABLED` (por defecto `false`): si no se habilita, el router no se
registra y el endpoint **no existe** ni aparece en el OpenAPI. Requiere el permiso
`payments:create`. Con `age_minutes: 0` se generan pagos frescos, útiles para comprobar que la
conciliación **no** los toca.

## Observabilidad: Prometheus y Grafana

El objetivo no es solo saber *si* la API responde, sino **en qué se va el tiempo y qué componente
consume más**, que es lo que evita perseguir problemas a ciegas en producción.

### Qué se mide

Se recogen tres niveles, para poder distinguir "la operación es lenta por lógica de negocio" de
"es lenta porque la base de datos está saturada":

**1. Nivel HTTP** — automático, vía `prometheus-fastapi-instrumentator`:

| Métrica | Para qué sirve |
| --- | --- |
| `http_request_duration_seconds` (histograma) | Latencia por método, ruta y código de estado |
| `http_requests_total` | Volumen y tasa de errores (`status=~"5.."`) |

**2. Nivel de negocio** — instrumentación propia, lo que un dashboard genérico no da:

| Métrica | Qué responde |
| --- | --- |
| `payments_usecase_duration_seconds{operation}` | Cuánto tarda **cada caso de uso** (`create_payment`, `login_user`…), sin el ruido del overhead HTTP |
| `payments_idempotency_conflicts_total` | Cuántas veces dos peticiones compitieron por la misma `Idempotency-Key`. Si sube de golpe, alguien está reintentando en exceso |
| `payments_status_transitions_total{from_status,to_status}` | Flujo real del negocio: cuántos pagos se aprueban, se rechazan o se cancelan |
| `payments_reconciliation_processed_total` | Cuántos pagos rechazó la conciliación. Un salto indica que los pagos se están quedando colgados |

**3. Nivel de infraestructura** — `postgres-exporter` y `redis-exporter`: conexiones activas,
operaciones por segundo y uso de memoria.

Prometheus recoge (*scrape*) cuatro objetivos cada 15 s: la API, el worker y los dos exporters.

### Cómo se lee el dashboard

Grafana levanta con el dashboard **Payment Processing — Overview** ya provisionado, dividido en
tres filas: HTTP, casos de uso y negocio, e infraestructura.

**Los percentiles son lo más importante.** Cada línea responde "¿qué tan lento fue el request
número N de cada 100, ordenados de más rápido a más lento?":

| Línea | Significado |
| --- | --- |
| **p50** (mediana) | La mitad de las peticiones fue más rápida. Es la experiencia *típica* |
| **p95** | El 5 % peor fue más lento que esto |
| **p99** | El 1 % peor: los casos extremos |

Lo que importa no es cada número aislado, sino **la distancia entre ellos**. Un p50 de 7 ms con un
p99 de 240 ms significa "casi todo vuela, pero hay una cola lenta". Por eso se usan percentiles y
no el promedio: un promedio de ~20 ms escondería que hay usuarios esperando 240 ms.

**Ejemplo real de este proyecto.** Al mirar la duración por caso de uso aparece esto:

```
286.08 ms  login_user
 18.29 ms  reconcile_pending_payments
  3.68 ms  create_merchant
  3.31 ms  transition_payment_status
  0.76 ms  create_payment
```

La cola del p99 la domina `login`, y **es intencional**: el hash de contraseñas con bcrypt es
deliberadamente lento para encarecer los ataques por fuerza bruta. Si el login bajara a 1 ms, eso
sí sería un problema de seguridad. Mientras tanto, el núcleo del negocio —registrar un pago—
tarda menos de un milisegundo. Esa conclusión, imposible de obtener sin medir por caso de uso, es
justamente lo que justifica la instrumentación.

Dos advertencias al interpretar las gráficas: los tramos planos son **ausencia de tráfico**, no
caídas; y con pocas muestras los percentiles son poco fiables, porque `histogram_quantile`
interpola dentro de un *bucket* y tiende a devolver el borde.

## Migraciones

Los modelos y sus migraciones viven en `payment-db-models`, un paquete **independiente y
publicable**. La razón es la del tercer actor del primer diagrama: si otro servicio necesita la
misma base de datos, instala el paquete en lugar de copiar los modelos.

Las migraciones están **desacopladas del servicio**: ni la API ni el worker las generan o aplican
al arrancar. En Docker se ejecutan como un paso propio (`migrate`) del que dependen los demás,
de modo que ningún proceso arranca contra un esquema desactualizado.

El **esquema se define en SQL plano** bajo
[`libs/payment-db-models/payment_db_models/alembic/sql/`](libs/payment-db-models/payment_db_models/alembic/sql/)
(`0001_initial.up.sql` / `0001_initial.down.sql`). Alembic aporta el versionado, el orden y el
`upgrade`/`downgrade`; cada revisión solo aplica su archivo `.sql`. Así el DDL queda legible y
revisable por un DBA sin leer código Python.

```bash
# Manual (local)
cd libs/payment-db-models
DATABASE_URL=postgresql+psycopg://payments:change_me@localhost:5432/payment_processing alembic upgrade head

# Nueva revisión: crear el par de archivos SQL en alembic/sql/ y una revisión que los aplique
alembic revision -m "describe change"   # editar el archivo para llamar run_sql_file(...)
```

> Los `.sql` iniciales se generaron a partir de los modelos SQLAlchemy para que coincidan
> exactamente con el esquema; a partir de ahí se versionan como SQL.

### Identificadores

Las llaves primarias son **UUID**, no enteros autoincrementales, y se generan en la aplicación.
Con secuencias, todas las instancias dependerían de un contador central; además, un identificador
secuencial revelaría el volumen de negocio y permitiría enumerar recursos ajenos. El costo
conocido es la localidad de índice, ya que UUID v4 es aleatorio; la evolución natural sería UUID
v7, ordenable en el tiempo.

## Pruebas

```bash
# Con Postgres y Redis disponibles (p. ej. `docker compose up -d postgres redis`)
pip install -e libs/payment-db-models -e "services/api[dev]" -e services/reconciliation
pytest
```

Las pruebas crean su propia base de datos (`payment_processing_test`) y aíslan cada caso. Cubren
la creación de pagos, el rechazo de valores inválidos, la idempotencia —incluida la **carrera
concurrente** de ocho peticiones simultáneas—, la referencia externa duplicada, las transiciones
válidas e inválidas, el resumen por comercio, la autenticación, el RBAC, la detección de reuso de
refresh token y la conciliación concurrente.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Registro de usuario (rol OPERATOR por defecto) |
| POST | `/api/v1/auth/login` | Login → access + refresh |
| POST | `/api/v1/auth/refresh` | Rotación de refresh token |
| POST | `/api/v1/merchants` | Crear comercio |
| GET | `/api/v1/merchants/{id}` | Consultar comercio |
| GET | `/api/v1/merchants/{id}/summary` | Resumen por comercio |
| POST | `/api/v1/payments` | Crear pago (`Idempotency-Key` obligatorio) |
| GET | `/api/v1/payments` | Listar con filtros y paginación |
| GET | `/api/v1/payments/{id}` | Consultar pago |
| PATCH | `/api/v1/payments/{id}/status` | Cambiar estado |
| GET | `/api/v1/payments/{id}/history` | Historial de estados |
| POST | `/api/v1/demo/payments/random` | Genera pagos de prueba (solo si está habilitado) |

Los errores usan un formato uniforme:

```json
{ "error": { "code": "INVALID_PAYMENT_STATUS", "message": "..." } }
```

Los códigos HTTP se usan con intención, distinguiendo *petición mal formada* de *petición válida
que incumple una regla*:

| Código | Cuándo | Código de error |
| --- | --- | --- |
| `200` | Consulta o actualización correcta | — |
| `201` | Recurso creado (también al reintentar con la misma `Idempotency-Key`) | — |
| `400` | El cuerpo no es JSON válido: la petición no se puede ni interpretar | `MALFORMED_REQUEST` |
| `401` | Sin credenciales, o sesión revocada/expirada | `AUTHENTICATION_REQUIRED`, `SESSION_EXPIRED` |
| `403` | Autenticado, pero sin el permiso necesario | `PERMISSION_DENIED` |
| `404` | El comercio o el pago no existe | `MERCHANT_NOT_FOUND`, `PAYMENT_NOT_FOUND` |
| `409` | Choque con un recurso existente | `DUPLICATE_EXTERNAL_REFERENCE`, `DUPLICATE_MERCHANT` |
| `422` | JSON bien formado pero inválido: importe ≤ 0, correo mal escrito, medio de pago inexistente o transición no permitida | `VALIDATION_ERROR`, `INVALID_PAYMENT_STATUS` |
| `500` | Error no controlado; nunca expone detalles internos | `INTERNAL_SERVER_ERROR` |

### Documentación interactiva

Swagger UI: http://localhost:8000/docs · OpenAPI JSON: http://localhost:8000/openapi.json

El OpenAPI declara los dos esquemas de seguridad (`userJWT` como *bearer* y `serviceApiKey` como
header `X-API-Key`), así que Swagger UI tiene botón **Authorize** y los clientes generados saben
cómo autenticarse.

### Colección de Postman

En [`docs/postman/`](docs/postman/) está la colección lista para importar
(`payment-processing.postman_collection.json`, formato v2.1):

1. Postman → *Import* → seleccionar el archivo.
2. Ejecutar **Auth → Login**: guarda `accessToken` y `refreshToken` en las variables de la
   colección automáticamente; el resto de peticiones heredan el bearer token.
3. **Merchants → Create merchant** y **Payments → Create payment** guardan `merchantId` y
   `paymentId`, de modo que las demás peticiones funcionan sin copiar UUID a mano.

Incluye también una consulta autenticada con API Key, para probar el escenario
servicio-a-servicio.

**Para demostrar la idempotencia** basta con enviar **dos veces** la petición *Create payment*: la
llave `Idempotency-Key` es fija (`payment-001`), así que la segunda respuesta devuelve el mismo
`id` que la primera en lugar de crear un pago nuevo.

```bash
npx newman run docs/postman/payment-processing.postman_collection.json
```

## Variables de entorno

Ver [`.env.example`](.env.example). Principales:

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Conexión PostgreSQL (`postgresql+psycopg://...`) |
| `REDIS_URL` | Redis para sesiones |
| `CELERY_BROKER_URL` | Redis como broker de Celery |
| `JWT_SECRET`, `JWT_ALGORITHM` | Firma de tokens |
| `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS` | Vigencia de tokens |
| `PENDING_TIMEOUT_MINUTES` | Umbral de conciliación (30 por defecto) |
| `RECONCILIATION_INTERVAL_SECONDS` | Frecuencia del scheduler |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrador inicial del seed |
| `SERVICE_API_KEY` | API Key de servicio a registrar (opcional) |
| `DEMO_ENDPOINTS_ENABLED` | Expone `/api/v1/demo/*` para generar datos de prueba (`false` en producción) |

## Decisiones técnicas

- **Clean Architecture en una sola aplicación.** Un único dominio sobre una sola base de datos;
  microservicios añadirían complejidad justo donde más importa la corrección (idempotencia y
  concurrencia) sin aportar valor. La separación en capas da el mismo desacoplamiento: el núcleo
  no conoce FastAPI ni SQLAlchemy, se prueba aislado y deja abierta la puerta a extraer servicios.

- **Precisión monetaria con `Decimal`.** Value object `Money`, validación `> 0`, persistencia en
  `NUMERIC(18,2)` y prohibición de `float` en todo el recorrido.

- **Idempotencia resuelta en la base de datos.** Restricción única más manejo del conflicto de
  inserción, en lugar de bloqueos explícitos: más simple y correcto también bajo concurrencia real.

- **Máquina de estados explícita en el dominio**, validada antes de persistir.

- **Modelos en un paquete reutilizable** (`payment-db-models`), con migraciones desacopladas del
  arranque de los servicios y DDL en SQL plano.

- **Autenticación en dos escenarios**: API Key con hash para sistemas y JWT para personas, con el
  actor registrado en cada cambio de estado.

- **Sesión única y anti-robo con Redis**, que además es el broker de Celery: doble propósito, sin
  infraestructura adicional.

- **RBAC persistido en base de datos**, evaluado en tiempo de ejecución, para no desplegar por
  cada cambio de permisos.

- **Conciliación segura ante múltiples instancias** mediante `FOR UPDATE SKIP LOCKED`, de modo que
  la corrección no dependa de que exista una sola réplica.

- **Observabilidad desde el primer día**, con métricas de negocio y no solo técnicas.

- **Tipado fuerte**: SQLAlchemy 2.0 (`Mapped[...]`), Pydantic v2 y `mypy` en modo estricto.

- **GitFlow como estrategia de ramas**, descrito a continuación.

## Flujo de trabajo con Git

El repositorio sigue **GitFlow**, de modo que el historial cuenta cómo se construyó el proyecto en
lugar de ser una lista plana de cambios.

```mermaid
gitGraph
    commit id: "init"
    branch develop
    checkout develop
    commit id: "db-models"
    branch feature/api
    checkout feature/api
    commit id: "dominio"
    commit id: "endpoints"
    checkout develop
    merge feature/api
    branch feature/observabilidad
    checkout feature/observabilidad
    commit id: "metricas"
    checkout develop
    merge feature/observabilidad
    checkout main
    merge develop tag: "v0.1.0"
```

| Rama | Propósito |
| --- | --- |
| `main` | Solo versiones liberadas y etiquetadas. Cada *merge* corresponde a una release |
| `develop` | Rama de integración: acumula el trabajo terminado hasta la siguiente release |
| `feature/*` | Una rama por unidad de trabajo, que nace de `develop` y vuelve a `develop` |

Las integraciones se hacen con `--no-ff` (sin *fast-forward*) para que el historial conserve la
agrupación por funcionalidad: se ve de un vistazo qué commits pertenecen a qué trabajo, y una
funcionalidad completa se revierte con un solo *revert* del *merge*.

### Convención de mensajes (gitmoji)

| Emoji | Tipo | Se usa para |
| --- | --- | --- |
| 🎉 | `init` | Commit inicial del proyecto |
| ✨ | `feat` | Funcionalidad nueva |
| 🗃️ | `db` | Modelos o migraciones de base de datos |
| 🔒️ | `security` | Autenticación, permisos, sesiones |
| 📈 | `metrics` | Instrumentación y observabilidad |
| 🐳 | `docker` | Contenedores y orquestación |
| ✅ | `test` | Pruebas automatizadas |
| 📝 | `docs` | Documentación |
| 🔧 | `config` | Configuración y tooling |
| 🔀 | `merge` | Integración de una rama |
| 🔖 | `release` | Versión etiquetada |

Ejemplo: `✨ feat(payments): idempotencia por restricción única y manejo de conflicto`

## Supuestos

- La recuperación de contraseña queda fuera del alcance funcional (no hay servicio de correo); el
  flujo de autenticación se centra en registro, login y rotación de sesión.
- La moneda se restringe a `COP`.
- La API Key de servicio se aprovisiona por seed; no hay endpoint de gestión.
- Un usuario registrado recibe el rol `OPERATOR`; la asignación de otros roles se hace por seed o
  base de datos.

## Limitaciones

- El worker de Celery corre con `--pool=solo` únicamente para que sus métricas queden en el mismo
  proceso; no es un límite de escalado (con `FOR UPDATE SKIP LOCKED` es seguro correr N workers).
  En producción se usaría el pool `prefork`.
- El scheduler debe desplegarse como réplica única, o con un lock distribuido tipo RedBeat.
- No hay integración con una pasarela real: el cambio de estado es manual o por conciliación.
- La gestión de roles, permisos y API Keys no tiene endpoints de administración.
