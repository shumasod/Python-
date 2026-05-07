.PHONY: help build up down logs test lint fmt

help:
	@echo "RDS Analyzer - 開発コマンド一覧"
	@echo ""
	@echo "  make build    コンテナイメージをビルド"
	@echo "  make up       全サービスを起動 (API + Frontend)"
	@echo "  make down     全サービスを停止"
	@echo "  make logs     ログを表示 (Ctrl+C で終了)"
	@echo "  make api      API のみ起動"
	@echo "  make test     テストを実行"
	@echo "  make lint     コードチェック (ruff)"
	@echo "  make fmt      コードフォーマット (ruff format)"
	@echo "  make clean    キャッシュ・ビルド生成物を削除"

build:
	docker compose build

up:
	docker compose up -d
	@echo "API:      http://localhost:8000/api/v1/health"
	@echo "Docs:     http://localhost:8000/docs"
	@echo "Frontend: http://localhost:5173"

down:
	docker compose down

logs:
	docker compose logs -f

api:
	docker compose up -d api
	@echo "API:  http://localhost:8000/api/v1/health"
	@echo "Docs: http://localhost:8000/docs"

test:
	python -m pytest tests/ -v --tb=short

lint:
	ruff check rds_analyzer/ tests/

fmt:
	ruff format rds_analyzer/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
