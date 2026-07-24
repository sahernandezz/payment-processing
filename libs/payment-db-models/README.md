# payment-db-models

Capa de base de datos compartida: modelos SQLAlchemy 2.0, enums y el entorno de migraciones
Alembic. Se empaqueta de forma independiente para que cualquier servicio (la API de pagos, el
worker de conciliación o servicios futuros) reutilice el mismo esquema sin duplicar los modelos.

## Migraciones

El paquete es dueño de sus migraciones. El esquema está escrito en **SQL plano** bajo
`payment_db_models/alembic/sql/`; cada revisión de Alembic únicamente aplica su archivo `.sql`
mediante `migrations_util.run_sql_file(...)`. Alembic aporta el versionado y el `upgrade` /
`downgrade`, mientras que el DDL permanece legible como SQL.

```bash
DATABASE_URL=postgresql+psycopg://usuario:clave@host:5432/basededatos alembic upgrade head
```

Para agregar un cambio: crear el par de archivos `NNNN_nombre.up.sql` / `.down.sql` y una revisión
que los aplique (`alembic revision -m "..."`, y luego editar `upgrade` / `downgrade` para llamar a
`run_sql_file`).
