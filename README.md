# Payment Processing API

API de procesamiento de pagos: comercios, pagos, historial de estados, resumen por comercio
y conciliación automática de pagos pendientes vencidos. Desarrollada en Python siguiendo los
principios de **Clean Architecture**.

## Descripción

La solución permite crear comercios, registrar pagos evitando duplicados, consultar y filtrar
pagos, cambiar su estado con transiciones controladas, consultar el historial de cada cambio,
obtener un resumen por comercio y ejecutar un proceso de conciliación que rechaza los pagos
que llevan demasiado tiempo en estado `PENDING`.

Incluye autenticación en dos escenarios (usuarios con JWT y servicios con API Key), RBAC con
roles y permisos en base de datos, control de idempotencia y concurrencia, precisión monetaria
con `Decimal`, y observabilidad con Prometheus y Grafana.

## Arquitectura

La aplicación se organiza en capas concéntricas siguiendo **Clean Architecture**: las
dependencias apuntan siempre hacia adentro, hacia el dominio. El núcleo no sabe que existe
FastAPI, Postgres ni Redis, de modo que las reglas de negocio se prueban y evolucionan sin
acoplarse a la tecnología.

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

Las dependencias siempre apuntan **hacia adentro**: cada capa conoce a la que envuelve, nunca al
revés. El núcleo (`domain/`) no sabe que existen FastAPI, PostgreSQL ni Redis.

| Capa | Responsabilidad | De qué **no** depende |
| --- | --- | --- |
| `domain/` | Reglas puras: value object `Money`, máquina de estados, errores de negocio, catálogo de permisos | De nada del framework ni de la base de datos |
| `application/` | Casos de uso que orquestan el dominio y persisten vía repositorios | De FastAPI ni de HTTP |
| `infrastructure/` | Implementaciones concretas: repositorios SQLAlchemy, Unit of Work, sesiones en Redis, JWT, métricas | — |
| `api/` | Transporte HTTP: routers, schemas Pydantic, autenticación y RBAC, manejo de errores | — |

La regla se cumple donde más importa: **`domain/` no importa nada de `infrastructure/`**, por eso
las reglas de negocio se testean sin base de datos. Como decisión pragmática, `application/`
recibe el `UnitOfWork` concreto en lugar de una interfaz: con un único motor de persistencia, la
inversión de dependencias completa añadiría indirección sin beneficio real. Si mañana hubiera que
soportar otro almacenamiento, ahí sí se extraería el puerto.

### Estructura del repositorio

```
libs/
  payment-db-models/        Paquete independiente: modelos SQLAlchemy + migraciones Alembic
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

### Contenedores

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

Todos los diagramas están escritos en Mermaid dentro de este README, así que GitHub los renderiza
directamente y no hay imágenes que se desactualicen. Para editarlos gráficamente, basta copiar el
bloque a Excalidraw (`Insert → Mermaid`).

## Diagramas

### C4 Nivel 1 — Contexto

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

### C4 Nivel 3 — Componentes (contenedor API)

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

### Proceso — Creación de pago con idempotencia bajo concurrencia

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

### Proceso — Máquina de estados del pago

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

### Proceso — Autenticación: sesión única, rotación y detección de robo

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

### Proceso — Conciliación de pagos pendientes vencidos

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

## Requisitos

- Docker y Docker Compose (única dependencia para levantar todo el stack).
- Para desarrollo local sin Docker: Python 3.12+, PostgreSQL y Redis.

## Instalación y ejecución

```bash
cp .env.example .env
docker compose up --build
```

El arranque ejecuta, en orden: migraciones (`migrate`), seed de roles/permisos/admin (`seed`)
y luego API, worker y beat. Servicios expuestos:

| Servicio        | URL                              |
| --------------- | -------------------------------- |
| API             | http://localhost:8000            |
| Swagger / OpenAPI | http://localhost:8000/docs     |
| Métricas API    | http://localhost:8000/metrics    |
| Prometheus      | http://localhost:9090            |
| Grafana         | http://localhost:3000 (admin/admin) |

En Grafana, el dashboard **Payment Processing — Overview** queda provisionado automáticamente.

### Uso rápido

```bash
# 1. Login como admin (creado por el seed)
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@payments.com","password":"admin12345"}' | jq -r .access_token)

# 2. Crear comercio
curl -X POST localhost:8000/api/v1/merchants -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Comercio Prueba","document_number":"900123456","email":"c@example.com"}'

# 3. Crear pago (Idempotency-Key obligatorio)
curl -X POST localhost:8000/api/v1/payments -H "Authorization: Bearer $TOKEN" \
  -H 'Idempotency-Key: payment-001' -H 'Content-Type: application/json' \
  -d '{"merchant_id":"<uuid>","external_reference":"ORDER-1001","amount":150000,"currency":"COP","payment_method":"QR"}'
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
| `PENDING_TIMEOUT_MINUTES` | Umbral de conciliación (default 30) |
| `RECONCILIATION_INTERVAL_SECONDS` | Frecuencia del beat |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin bootstrap del seed |
| `DEMO_ENDPOINTS_ENABLED` | Expone `/api/v1/demo/*` para generar datos de prueba (`false` en prod) |
| `SERVICE_API_KEY` | API Key de servicio a registrar (opcional) |

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

## Autenticación, usuarios, roles y permisos

### Los dos tipos de consumidor

La API distingue **quién** llama, porque no es lo mismo una persona operando el back office que
otro sistema integrado. Cada endpoint protegido acepta cualquiera de los dos mecanismos.

| | Usuario (persona) | Servicio (sistema) |
| --- | --- | --- |
| Mecanismo | JWT (`Authorization: Bearer <token>`) | API Key (`X-API-Key: <clave>`) |
| Cómo se obtiene | `POST /api/v1/auth/login` | Se aprovisiona por seed (`SERVICE_API_KEY`) |
| Vigencia | Access token corto + refresh rotativo | Estática hasta revocarla |
| Permisos | Los de sus roles en base de datos | Conjunto fijo de servicio |
| Sesión | Única por usuario, revocable al instante | Sin sesión (no aplica) |
| Queda registrado como | `user:<uuid>` | `service:<uuid>` |

Ese último punto es el que conecta con la trazabilidad: el campo `changed_by` del historial
guarda exactamente quién cambió cada estado, sea persona o sistema.

### Catálogo de permisos

Los permisos son **filas en la base de datos** (tabla `permissions`), no un enum en el código,
y se evalúan en tiempo de ejecución:

| Permiso | Autoriza a |
| --- | --- |
| `merchants:create` | Crear comercios |
| `merchants:read` | Consultar comercios y su resumen |
| `payments:create` | Registrar pagos (y generar los de demo) |
| `payments:read` | Consultar y listar pagos e historial |
| `payments:transition` | Cambiar el estado de un pago |
| `roles:manage` | Administrar roles y permisos |

### Roles incluidos en el seed

Un rol es un conjunto de permisos (`roles` ↔ `permissions`, relación muchos a muchos):

| Rol | Permisos | Para quién |
| --- | --- | --- |
| **ADMIN** | Todos los anteriores | Administración: crear comercios, cambiar estados, gestionar roles |
| **OPERATOR** | `merchants:read`, `payments:create`, `payments:read` | Operación diaria: registrar y consultar, **sin** poder aprobar ni rechazar |
| *(servicio)* | `merchants:read`, `payments:create`, `payments:read`, `payments:transition` | Integraciones automáticas. No es un rol en BD: es el conjunto fijo que se asigna al autenticar por API Key |

Quien se registra por `POST /api/v1/auth/register` recibe **OPERATOR** por defecto. La separación
importa: un operador puede registrar pagos, pero **no** aprobarlos — eso exige `payments:transition`
y es justo lo que verifica el test `test_operator_cannot_create_merchant`.

Un permiso faltante devuelve `403 PERMISSION_DENIED`; la ausencia total de credenciales,
`401 AUTHENTICATION_REQUIRED`.

### Sesión única y protección ante robo de token

El login guarda la sesión en Redis bajo `session:{user_id}`. Como la clave es una sola por
usuario, **un login nuevo sobrescribe el anterior**: solo hay una sesión activa. El access token
lleva dentro un identificador de sesión (`sid`) que se valida contra Redis en cada petición, de
modo que revocar una sesión surte efecto de inmediato sin esperar a que expire el token.

El refresh token **rota en cada uso**. Si llega uno ya rotado, se interpreta como robo (alguien
está reusando un token viejo) y se elimina la sesión completa, forzando a iniciar sesión de nuevo.

## Worker de conciliación

El proceso rechaza automáticamente los pagos que llevan más de `PENDING_TIMEOUT_MINUTES`
(30 por defecto) en estado `PENDING`.

### Dos procesos separados: quién programa y quién ejecuta

Celery separa **el reloj** del **ejecutor**, y por eso son dos contenedores distintos:

| Contenedor | Comando que ejecuta | Qué hace |
| --- | --- | --- |
| `reconciliation-beat` | `celery -A worker.celery_app beat --loglevel=info` | Es el *scheduler* (equivale a un cron). Cada `RECONCILIATION_INTERVAL_SECONDS` publica un mensaje en Redis. **No toca la base de datos.** |
| `reconciliation-worker` | `celery -A worker.celery_app worker --pool=solo --loglevel=info` | Consume el mensaje y **hace el trabajo real**: consulta, actualiza estados, escribe historial y expone métricas en el puerto `9808`. |

El traspaso se ve en los logs, con Redis en medio:

```
beat    | Scheduler: Sending due task reconcile-pending-payments
worker  | Task worker.tasks.reconcile_pending_payments[...] received
worker  | Reconciliation rejected 3 stale pending payments
worker  | Task ... succeeded in 0.016s: 3
```

Qué hace el worker en cada corrida:

1. Selecciona los pagos `PENDING` cuyo `created_at` supera la ventana permitida.
2. Los pasa a `REJECTED`.
3. Registra el cambio en el historial con `changed_by = service:reconciliation`.
4. Incrementa `payments_reconciliation_processed_total` y devuelve cuántos procesó.

### Escalado y ejecución concurrente

Los **workers escalan horizontalmente**: se pueden correr N contenedores repartiéndose la carga.
El **scheduler debe ser único** (si hay tres, el job se dispara tres veces), igual que cualquier
cron. Aun así, la corrección **no depende** de eso: la consulta usa
`SELECT ... FOR UPDATE SKIP LOCKED`, de modo que si varias corridas coinciden, cada transacción
toma un subconjunto distinto de filas y las demás saltan las bloqueadas. Cada pago se procesa
**exactamente una vez**, sin historial duplicado.

`--pool=solo` está puesto solo para que las métricas queden en el mismo proceso que las expone;
no es un límite de escalado. En producción se usaría el pool `prefork`.

### Ejecutar la conciliación a demanda

Para no esperar al scheduler, el mismo caso de uso se puede invocar como script de una sola
corrida (útil en demos y como *cron job* del sistema):

```bash
docker compose run --rm reconciliation-worker python -m worker.run_once
# -> Reconciliation rejected 3 stale pending payments
```

### Generar pagos vencidos para probarlo

Para no esperar media hora, hay un endpoint que genera pagos aleatorios **ya vencidos**: monto y
medio de pago al azar, asignados a un comercio existente elegido al azar, con `created_at`
retrocedido.

```bash
# 1. Generar 3 pagos PENDING con 45 minutos de antigüedad
curl -X POST localhost:8000/api/v1/demo/payments/random \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"count": 3, "age_minutes": 45}'

# 2. Ejecutar la conciliación sin esperar al scheduler
docker compose run --rm reconciliation-worker python -m worker.run_once
# -> Reconciliation rejected 3 stale pending payments
```

El historial del pago queda así, mostrando los dos actores:

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

Prometheus recoge (*scrape*) cuatro objetivos cada 15 s: la API, el worker, y los dos exporters.

### Cómo se lee el dashboard

Grafana levanta con el dashboard **Payment Processing — Overview** ya provisionado
(http://localhost:3000, `admin` / `admin`). Está dividido en tres filas: HTTP, casos de uso y
negocio, e infraestructura.

**Los percentiles son lo más importante.** Cada línea responde "¿qué tan lento fue el request
número N de cada 100, ordenados de más rápido a más lento?":

| Línea | Significado |
| --- | --- |
| **p50** (mediana) | La mitad de las peticiones fue más rápida. Es la experiencia *típica* |
| **p95** | El 5 % peor fue más lento que esto |
| **p99** | El 1 % peor: los casos extremos |

Lo que importa no es cada número aislado, sino **la distancia entre ellos**. Un p50 de 7 ms con
un p99 de 240 ms significa "casi todo vuela, pero hay una cola lenta". Por eso se usan
percentiles y no el promedio: un promedio de ~20 ms escondería que hay usuarios esperando 240 ms.

**Ejemplo real de este proyecto.** Al mirar la duración por caso de uso aparece esto:

```
286.08 ms  login_user
 18.29 ms  reconcile_pending_payments
  3.68 ms  create_merchant
  3.31 ms  transition_payment_status
  0.76 ms  create_payment
```

La cola del p99 la domina `login`, y **es intencional**: el hash de contraseñas con bcrypt es
deliberadamente lento para encarecer los ataques por fuerza bruta. Si el login bajara a 1 ms,
eso sí sería un problema de seguridad. Mientras tanto, el núcleo del negocio —registrar un
pago— tarda menos de un milisegundo. Esa conclusión, imposible de obtener sin medir por caso de
uso, es justamente lo que justifica la instrumentación.

Dos advertencias al interpretar las gráficas: los tramos planos son **ausencia de tráfico**, no
caídas; y con pocas muestras los percentiles son poco fiables, porque `histogram_quantile`
interpola dentro de un *bucket* y tiende a devolver el borde.

## Migraciones

Las migraciones viven en el paquete `payment-db-models`, **desacopladas del servicio**: ni la API
ni el worker las generan o aplican en su arranque. En Docker se corren como un paso propio
(`migrate`) del que dependen los demás servicios.

El **esquema se define en SQL plano** bajo
[`libs/payment-db-models/payment_db_models/alembic/sql/`](libs/payment-db-models/payment_db_models/alembic/sql/)
(`0001_initial.up.sql` / `0001_initial.down.sql`). Alembic aporta el versionado, el orden y el
`upgrade/downgrade`; cada revisión solo aplica su archivo `.sql` (ver
`alembic/versions/0001_initial_schema.py`). Así el DDL queda legible y revisable por un DBA sin
leer código Python.

```bash
# Manual (local)
cd libs/payment-db-models
DATABASE_URL=postgresql+psycopg://payments:change_me@localhost:5432/payment_processing alembic upgrade head

# Nueva revisión: crear el par de archivos SQL en alembic/sql/ y una revisión que los aplique
alembic revision -m "describe change"   # editar el archivo para llamar run_sql_file(...)
```

> Los `.sql` iniciales se generaron a partir de los modelos SQLAlchemy (fuente de verdad) para
> que coincidan exactamente con el esquema; a partir de ahí se versionan como SQL.

## Pruebas

```bash
# Con Postgres y Redis disponibles (p. ej. `docker compose up -d postgres redis`)
pip install -e libs/payment-db-models -e "services/api[dev]" -e services/reconciliation
pytest
```

Las pruebas crean su propia base de datos de test (`payment_processing_test`) y aíslan cada caso. Cubren:
creación de pago, valores inválidos, idempotencia (incluida la **carrera concurrente**),
referencia externa duplicada, transiciones válidas e inválidas, resumen, autenticación, RBAC,
rotación con detección de reuso y conciliación.

## Decisiones técnicas

- **Clean Architecture en una sola aplicación.** El reto es un único dominio sobre una sola base
  de datos; microservicios añadirían complejidad justo donde más pesa la evaluación
  (idempotencia y concurrencia) sin aportar valor. En su lugar, la separación en capas con las
  dependencias apuntando al dominio da el mismo desacoplamiento: el núcleo de negocio no conoce
  FastAPI ni SQLAlchemy, se testea aislado y deja abierta la puerta a extraer servicios si algún
  día se justifica.

- **GitFlow como estrategia de ramas.** `main` contiene solo versiones liberadas y etiquetadas;
  `develop` integra el trabajo en curso; cada unidad de trabajo vive en su propia rama
  `feature/*` y se integra con *merge* sin *fast-forward* (`--no-ff`) para que el historial
  conserve la agrupación por funcionalidad en vez de una lista plana de commits. Los mensajes
  siguen *gitmoji* (`✨ feat`, `🐛 fix`, `📝 docs`, `✅ test`…), lo que permite leer el propósito
  de cada commit de un vistazo. Ver [Flujo de trabajo con Git](#flujo-de-trabajo-con-git).

- **Precisión monetaria con `Decimal`.** Los importes se modelan con un value object `Money`,
  se validan `> 0`, se transportan como `Decimal` y se persisten en `NUMERIC(18,2)`. Nunca se
  usa `float`, evitando errores de redondeo en dinero.

- **Idempotencia y concurrencia.** `idempotency_key` y `(merchant_id, external_reference)` tienen
  restricción única en base de datos. La creación intenta el `INSERT` dentro de una transacción;
  si dos solicitudes concurrentes usan la misma llave, una gana y la otra recibe `IntegrityError`,
  hace rollback y devuelve el pago ya creado. Así se garantiza un único pago sin bloqueos
  explícitos. La referencia externa duplicada se traduce a `409 Conflict`.

- **Máquina de estados explícita.** Las transiciones válidas (`PENDING → APPROVED|REJECTED|CANCELLED`)
  viven en el dominio y se validan antes de tocar la base de datos; cualquier otra da `422`.

- **Modelos en un paquete reutilizable (`payment-db-models`).** El esquema y sus migraciones se
  empaquetan aparte para que otro servicio interno pueda reutilizarlos sin duplicar código. En este
  monorepo se instala como dependencia local; en producción se publicaría a un índice privado.

- **Autenticación en dos escenarios.** API Key (hash almacenado) para servicio-a-servicio; JWT
  para usuarios. El campo `changed_by` del historial registra `user:<id>` o `service:<api_key_id>`.

- **Sesión única y anti-robo con Redis.** La sesión vive en `session:{user_id}` en Redis; un nuevo
  login sobrescribe la anterior (sesión única). El access token lleva un `sid` que se valida contra
  Redis en cada request (revocación instantánea). El refresh rota en cada uso; si se reintenta un
  refresh ya rotado se asume robo y se elimina la sesión. Redis es el mismo que usa Celery como
  broker: doble propósito, sin infraestructura extra.

- **RBAC en base de datos.** `Role` y `Permission` son entidades con relación muchos-a-muchos; los
  permisos se evalúan en runtime. Roles semilla: `ADMIN` (todos) y `OPERATOR` (lectura + crear pago).

- **Conciliación segura ante múltiples instancias.** La consulta de pagos vencidos usa
  `SELECT ... FOR UPDATE SKIP LOCKED`, de modo que si varios workers (o instancias de beat
  duplicadas) ejecutan el job a la vez, cada transacción toma un subconjunto disjunto de filas y
  las demás saltan las bloqueadas: cada pago se procesa **exactamente una vez**, sin historial
  duplicado. Así la corrección no depende de que exista una sola instancia. Los *workers* escalan
  horizontalmente sin problema; el *scheduler* (beat) se despliega como réplica única (patrón
  estándar tipo cron), pero aunque se duplicara, el bloqueo de fila hace inofensivo el disparo doble.

- **Observabilidad (Prometheus + Grafana).** La API expone `/metrics` (latencia HTTP por endpoint),
  cada caso de uso se mide con un histograma `payments_usecase_duration_seconds{operation}` y hay
  métricas de negocio (conflictos de idempotencia, transiciones, pagos conciliados). Se incluyen
  `postgres-exporter` y `redis-exporter` para el nivel de infraestructura. El dashboard de Grafana
  se provisiona automáticamente. Permite identificar dónde se va el tiempo y qué consume más.

- **Tipado fuerte.** SQLAlchemy 2.0 tipado (`Mapped[...]`), Pydantic v2 y configuración de `mypy`
  estricto.

## Flujo de trabajo con Git

El repositorio sigue **GitFlow**, de modo que el historial cuenta cómo se construyó el proyecto
en lugar de ser una lista plana de cambios.

```mermaid
gitGraph
    commit id: "chore: init"
    branch develop
    checkout develop
    commit id: "feat: db-models"
    branch feature/api
    checkout feature/api
    commit id: "feat: dominio"
    commit id: "feat: endpoints"
    checkout develop
    merge feature/api
    branch feature/observabilidad
    checkout feature/observabilidad
    commit id: "feat: metricas"
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
agrupación por funcionalidad: se puede ver de un vistazo qué commits pertenecen a qué trabajo, y
revertir una funcionalidad completa con un solo *revert* del *merge*.

### Convención de mensajes (gitmoji)

Cada mensaje empieza con un emoji que identifica el tipo de cambio, seguido del ámbito:

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

Ejemplo: `✨ feat(payments): idempotencia por restricción única y manejo de conflicto`

## Supuestos

- La recuperación de contraseña queda fuera del alcance funcional (no hay servicio de correo); el
  flujo de auth se centra en registro, login y rotación de sesión.
- La moneda se restringe a `COP`, como indica el reto.
- La API Key de servicio se aprovisiona vía seed (`SERVICE_API_KEY`); no hay endpoint de gestión.
- Un usuario registrado recibe el rol `OPERATOR`; la asignación de otros roles se hace vía seed/DB.

## Limitaciones

- El worker de Celery corre con `--pool=solo` únicamente para que sus métricas Prometheus queden en
  el mismo proceso; no es un límite de escalado: se pueden correr N contenedores worker (y con el
  job idempotente por `FOR UPDATE SKIP LOCKED`, es seguro). En producción se usaría el pool `prefork`.
- El scheduler `beat` debe desplegarse como réplica única (o con un lock distribuido tipo RedBeat);
  el `docker-compose` de este repo corre una sola instancia de cada servicio.
- No hay integración con una pasarela real; el cambio de estado es manual o por conciliación.
- La gestión de roles/permisos y de API Keys no tiene endpoints de administración (se opera por seed
  o base de datos).

## Documentación de la API

Swagger UI: http://localhost:8000/docs · OpenAPI JSON: http://localhost:8000/openapi.json

El OpenAPI declara los dos esquemas de seguridad (`userJWT` como *bearer* y `serviceApiKey` como
header `X-API-Key`), así que Swagger UI tiene botón **Authorize** y los clientes generados saben
cómo autenticarse.

### Colección de Postman

En [`docs/postman/`](docs/postman/) está la colección lista para importar
(`payment-processing.postman_collection.json`, formato v2.1):

1. Postman → *Import* → seleccionar el archivo.
2. Ejecutar **Auth → Login**: guarda `accessToken` y `refreshToken` en las variables de la colección
   automáticamente; el resto de requests ya heredan el bearer token.
3. **Merchants → Create merchant** y **Payments → Create payment** guardan `merchantId` y
   `paymentId`, de modo que los demás requests funcionan sin copiar UUIDs a mano.

Incluye el caso de *replay* con la misma `Idempotency-Key` y una consulta autenticada con API Key
(escenario servicio-a-servicio). Variables configurables: `baseUrl`, `adminEmail`, `adminPassword`,
`serviceApiKey`, `idempotencyKey`.

La colección se regenera con `python -m scripts.generate_postman` y se puede ejecutar completa
desde consola:

```bash
npx newman run docs/postman/payment-processing.postman_collection.json
```

> Nota: FastAPI emite **OpenAPI 3.1**. Si tu versión de Postman falla al importar el
> `openapi.json`, usa la colección de arriba (el reto acepta cualquiera de las dos).
