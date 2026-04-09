# ============================================================
# 競艇予想AI - Makefile
# 使い方: make <target>
# ============================================================

.PHONY: help install train serve test lint fmt docker-build docker-up docker-down simulate backtest clean

PYTHON   := python
UVICORN  := uvicorn
PYTEST   := pytest
RUFF     := ruff

# デフォルトターゲット: ヘルプ表示
help:
	@echo "============================================"
	@echo " 競艇予想AI - 利用可能なコマンド"
	@echo "============================================"
	@echo "  make install       依存パッケージのインストール"
	@echo "  make train         サンプルデータでモデル学習"
	@echo "  make train-real    実データ(data/training.csv)でモデル学習"
	@echo "  make serve         APIサーバー起動（開発モード）"
	@echo "  make test          テスト実行"
	@echo "  make test-cov      カバレッジ付きテスト"
	@echo "  make lint          Ruff リント"
	@echo "  make fmt           Ruff フォーマット"
	@echo "  make simulate      回収率シミュレーション実行"
	@echo "  make backtest      バックテスト実行"
	@echo "  make scrape        スクレイパードライラン"
	@echo "  make docker-build  Docker イメージビルド"
	@echo "  make docker-up     docker compose 起動"
	@echo "  make docker-down   docker compose 停止"
	@echo "  make clean         生成ファイルの削除"
	@echo "============================================"

# ---- セットアップ ----

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pytest pytest-cov httpx ruff

# ---- モデル学習 ----

train:
	$(PYTHON) scripts/train_model.py --use-sample --n-races 2000

train-real:
	$(PYTHON) scripts/train_model.py --data-path data/training.csv

# ---- APIサーバー ----

serve:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

# ---- テスト ----

test:
	$(PYTEST) tests/ -v --tb=short

test-cov:
	$(PYTEST) tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-fast:
	$(PYTEST) tests/ -v -m "not slow and not integration"

# ---- コード品質 ----

lint:
	$(RUFF) check app/ scripts/ tests/

fmt:
	$(RUFF) format app/ scripts/ tests/
	$(RUFF) check --fix app/ scripts/ tests/

# ---- シミュレーター・バックテスト ----

simulate:
	$(PYTHON) simulator.py --n-races 300 --ev-threshold 1.0 --kelly-frac 0.5

backtest:
	$(PYTHON) backtester.py --n-races 500

scrape:
	$(PYTHON) scraper.py --dry-run --target results

# ---- Docker ----

docker-build:
	docker build -t boat-race-ai:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

docker-train:
	docker compose --profile train up trainer

# ---- クリーンアップ ----

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
	@echo "クリーンアップ完了"
