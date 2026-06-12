# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active Development Branch

All RDS Analyzer work lives on `claude/rds-analysis-tool-HDRuH`. Do **not** push to `main` without explicit instruction.

## Commands

### Tests

```bash
# Full suite with coverage (target ≥50% on rds_analyzer/)
python -m pytest tests/

# Single file
python -m pytest tests/test_cost_analyzer.py -v

# Single test
python -m pytest tests/test_cost_analyzer.py::TestStorageCost::test_gp2_to_gp3_savings_positive -v

# Skip coverage (faster)
python -m pytest tests/ --no-cov -q

# Run by marker
python -m pytest -m unit
python -m pytest -m "not slow"
```

### Backend

```bash
pip install -r rds_analyzer/requirements.txt
uvicorn rds_analyzer.main:app --reload
# Swagger UI → http://localhost:8000/docs
```

### Docker (local full-stack)

```bash
make up          # API (port 8000) + nginx frontend (port 80)
make dev         # API + Vite HMR frontend (port 5173)
make down
make logs
make test        # runs pytest inside host Python env
```

### Lint / Format

```bash
ruff check rds_analyzer/ tests/
ruff format rds_analyzer/ tests/
```

## Architecture

### rds_analyzer package

```
models/      → Pydantic v2 data models (no business logic)
analyzers/   → Pure computation engines (no I/O)
collectors/  → AWS API wrappers (boto3; always mock in tests)
api/         → FastAPI routes + request/response schemas
notifications/ → Slack Incoming Webhook client
report_generator.py → Markdown report builder
main.py      → FastAPI app, CORS, GZip, request-log middleware
```

**Data flow for a single analysis request:**

1. `POST /api/v1/rds` — registers `RDSInstance` in the in-memory `_instance_store`
2. `POST /api/v1/rds/{id}/metrics` — builds `MetricsHistory` and stores it in `_metrics_store`
3. `GET /api/v1/rds/{id}/analysis` — calls `CostAnalyzer.calculate_monthly_cost()`, `PerformanceAnalyzer.analyze()`, and `CostAnalyzer.calculate_efficiency_score()`; returns combined JSON

**Analyzer dependency graph:**

```
RDSInstance + MetricsHistory
    → CostAnalyzer         → CostBreakdown, CostEfficiencyScore
    → PerformanceAnalyzer  → PerformanceAnalysisResult
    → RecommendationEngine → list[Recommendation]   (needs both above)
    → MLAnomalyDetector    → AnomalyDetectionResult / CostForecast
    → ReportGenerator      → Markdown string        (needs all above)
```

### Key design constraints

- **All cost values are estimates** (ap-northeast-1 pricing). Every cost-facing string includes the word 推定値. Do not remove this disclaimer.
- **In-memory stores** (`_instance_store`, `_metrics_store`, `_cost_history_store` in `routes.py`) are intentional for development; production path uses DynamoDB.
- **No boto3 calls in tests** — all `collectors/` tests use `unittest.mock`. The `CloudWatchCollector` accepts an injected `boto3.Session` for this purpose.
- `PerformanceAnalyzer.get_iops_limit()` formula: gp2 = `max(100, allocated_gb × 3)`, capped at 16 000; gp3 = 3 000 default or `provisioned_iops`.
- CPU efficiency score: ideal range 20–80 %. Below 20 % penalises over-provisioning; above 80 % penalises bottleneck risk.

### Infrastructure / deployment

```
terraform/main.tf          → Lambda + DynamoDB + API Gateway + EventBridge
terraform/modules/multi_account/  → cross-account AssumeRole IAM resources
Dockerfile.rds-analyzer    → API container (python:3.12-slim, non-root)
Dockerfile.frontend        → React build → nginx:1.27-alpine
docker-compose.yml         → orchestrates both; --profile dev for Vite HMR
```

### Test layout

| File | Covers |
|------|--------|
| `test_cost_analyzer.py` | `CostAnalyzer`, `CostBreakdown`, `MonthlyCostReport` |
| `test_performance_analyzer.py` | `PerformanceAnalyzer` thresholds |
| `test_ml_anomaly.py` | `MLAnomalyDetector` Z-score + forecasting |
| `test_recommendation_engine.py` | `RecommendationEngine` all recommendation types |
| `test_report_generator.py` | `ReportGenerator` Markdown output |
| `test_slack_notifier.py` | `SlackNotifier` (HTTP mocked) |
| `test_api.py` | FastAPI endpoints via `TestClient` |
| `test_cloudwatch_collector.py` | `CloudWatchCollector` + `lambda_handler` (boto3 mocked) |
| `test_multi_account.py` | `MultiAccountCollector` (STS mocked) |
| `rds_conftest.py` | Shared `make_stats()` / `make_metrics()` helpers |

### Pricing constants location

`rds_analyzer/analyzers/cost_analyzer.py` top-level dicts:
- `INSTANCE_HOURLY_RATES` — On-Demand Single-AZ USD/hour per instance class
- `STORAGE_RATES` — USD/GB-month per `StorageType`
- `IOPS_RATES` — USD/IOPS-month for io1 and gp3 excess
- `INSTANCE_SPECS` — vCPU and memory_gb per class (used by recommendation text)

All rates are Tokyo region estimates. Update these dicts if pricing changes.
