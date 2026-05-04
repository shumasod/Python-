"""
アプリケーション設定・パス定数

ディレクトリパスをここに集約し、各モジュールから参照する。
テストでは各モジュールの変数を monkeypatch して一時ディレクトリに向ける。
"""
from pathlib import Path

# ---- データディレクトリ ----
DATA_DIR = Path("data")

PREDICTION_LOG_DIR = DATA_DIR / "prediction_logs"
RESULT_LOG_DIR     = DATA_DIR / "race_results"
SHADOW_LOG_DIR     = DATA_DIR / "shadow_logs"
AB_LOG_DIR         = DATA_DIR / "ab_test_logs"
DRIFT_REPORT_DIR   = DATA_DIR / "drift_reports"
SCRAPED_DIR        = DATA_DIR / "scraped"
ODDS_DIR           = DATA_DIR / "odds"

# ---- 学習データ ----
DEFAULT_TRAINING_CSV = DATA_DIR / "training.csv"
