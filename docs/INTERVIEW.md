# Interview walkthrough (15 minutes)

This is a **portfolio platform**. Do not claim it processes production bank volume.

## 1. Problem (1 min)

Partners send financial/regulatory feeds over CSV, REST, and webhooks. Downstream apps need one canonical JSON contract, not six partner shapes.

## 2. API-led design (3 min)

- **System API** — `POST /system/v1/feeds` with `Idempotency-Key` (safe retries).
- **Process API** — batch canonical load, webhook receiver, saga, event drain.
- **Experience API** — dashboard filters + GraphQL shim.

Login: `ananya` / `hub-demo` → JWT.

## 3. Events (3 min)

`hub/bus.py` is a file-backed Kafka stand-in: topics, event ids, inbox (dedupe), DLQ. In production this mapping is MSK/Confluent. Show `data/bus/` after an ingest.

## 4. Saga (3 min)

`start_saga`: validate → canonicalize → route → persist → notify. Negative amount compensates (delete + `feeds.failed`).

## 5. Spark (2 min)

`python spark-pipeline/jobs/ingest_feeds.py --pandas` builds 800 canonical records. Quality job exits non-zero on domain violations.

## 6. .NET (2 min)

`api/Program.cs` still serves REST over the Spark JSON for a C# system-layer story. CI builds it on GitHub-hosted runners.

## Honest limits

- SQLite + file bus, not Kafka/Postgres until docker/k8s swap.
- Demo JWT secret.
- Synthetic 800-row dataset.
