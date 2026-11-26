# GeneWeaver Background Workers

## Overview

GeneWeaver uses Celery with Redis as its task broker for asynchronous
alignment-job processing.

PostgreSQL remains the source of truth for:

- Alignment job status
- Job progress
- Scientific parameters
- Alignment results
- Error information
- Execution timestamps

Redis transports tasks between the API and workers. Celery task results
are not stored in Redis because genomic result data belongs in PostgreSQL.

## Architecture

```text
Client
  |
  v
FastAPI
  |
  | Create alignment job in PostgreSQL
  | Enqueue job UUID
  v
Redis
  |
  v
Celery Worker
  |
  | Load job from PostgreSQL
  | Claim pending job
  | Execute configured processor
  | Persist status and results
  v
PostgreSQL