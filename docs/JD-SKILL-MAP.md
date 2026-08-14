# Skill map vs 2026 job postings

Sources: Qarera 360k-posting report (Dec 2025–Jun 2026), 48k software-engineer posting analysis, LinkedIn/integration-developer guides. This repo implements the **concepts**, not fake production traffic.

| Company-requested concept | Where it lives in this repo |
|:--|:--|
| REST APIs / OpenAPI | `hub/app.py`, FastAPI `/docs` |
| JavaScript dashboards | `dashboard/app.js` |
| C# / .NET | `api/Program.cs` ASP.NET Core 8 |
| Python | `hub/`, Spark jobs, tests |
| SQL | SQLite schema in `hub/db.py` (Postgres-ready) |
| Microservices | gateway + process-api + ingest-api + worker |
| API gateway | `hub/gateway.py` |
| JWT / OAuth-style auth | `hub/security.py` |
| Kafka / event streaming | `hub/bus.py` topic files + DLQ; Kafka-shaped envelope |
| Spark | `spark-pipeline/jobs/ingest_feeds.py` |
| Docker | `Dockerfile`, `docker-compose.yml` |
| Kubernetes | `k8s/process-api.yaml` |
| CI/CD | `.github/workflows/ci.yml` |
| Terraform / IaC | `terraform/main.tf` |
| Observability | `/health`, `/metrics`, audit table |
| Testing | `tests/` pytest |
| GraphQL | `/experience/v1/graphql` |
| gRPC | `proto/feeds.proto` |
| Webhooks | `POST /process/v1/webhooks` |
| Idempotency | `Idempotency-Key` |
| Saga / compensation | `hub/sagas.py` |
| Circuit breaker | `hub/sagas.py` |
| Rate limiting | `hub/security.py` |
| Data quality | `spark-pipeline/jobs/quality_checks.py` |
| System design | `docs/ARCHITECTURE.md`, `docs/INTERVIEW.md` |
