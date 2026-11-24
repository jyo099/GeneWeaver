
# GeneWeaver Database Migrations

## Overview

GeneWeaver uses Alembic to manage database schema changes.

Migration files are stored in:

- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/`

The initial migration creates:

- `alignment_jobs`
- `alignment_results`
- The foreign-key relationship between both tables
- Database constraints and query indexes

## Database configuration

Alembic uses the existing GeneWeaver application configuration.

Set the database URL through the `GW_DATABASE_URL` environment variable
or the project's `.env` file.

Example:

```env
GW_DATABASE_URL=postgresql+psycopg://geneweaver:your-password@localhost:5432/geneweaver
```

Do not commit real database passwords or production connection strings.

## Apply migrations

Check the current migration version:

```powershell
alembic current
```

Upgrade the database to the latest migration:

```powershell
alembic upgrade head
```

List migration history:

```powershell
alembic history
```

## Create a future migration

After changing SQLAlchemy models, generate a migration:

```powershell
alembic revision --autogenerate -m "describe schema change"
```

Review the generated migration before applying it.

Autogeneration is a starting point, not a guarantee that every schema
change has been detected or represented correctly.

Apply the reviewed migration:

```powershell
alembic upgrade head
```

## Roll back migrations

Show the current migration:

```powershell
alembic current
```

Roll back one revision:

```powershell
alembic downgrade -1
```

Roll back all migrations:

```powershell
alembic downgrade base
```

Only roll back production migrations after reviewing the data impact
and confirming that a suitable backup exists.

## Offline SQL generation

Generate SQL for upgrading to the latest revision without connecting
to the database:

```powershell
alembic upgrade head --sql
```

Review the generated SQL before executing it manually.

## Production deployment

Recommended deployment sequence:

1. Back up the database.
2. Review pending migration files.
3. Apply migrations through the deployment process.
4. Verify the migration version.
5. Start or restart application workers.
6. Verify application health and database access.

Do not run `Base.metadata.create_all()` as a substitute for
production migrations.

## Testing

Run migration tests:

```powershell
pytest tests/unit/test_migrations.py -v
```

Run all tests:

```powershell
pytest -v
```
