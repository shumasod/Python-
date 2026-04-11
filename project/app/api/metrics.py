"""
Prometheus メトリクス エクスポーター
GET /metrics で Prometheus 形式のメトリクスを返す

必要パッケージ: prometheus-client
  pip install prometheus-client

計測項目:
  - predict_requests_total       : 予測リクエスト数（ラベル: status）
  - predict_latency_seconds      : 予測処理時間ヒストグラム
  - model_version_info           : 現在の本番モデルバージョン
  - active_model_loaded          : モデルキャッシュのロード状態
"""
import time
from typing import Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# prometheus_client を条件付きインポート
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        REGISTRY,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus-client が未インストールです。pip install prometheus-client を実行してください。")


# ---- メトリクス定義 ----

if _PROMETHEUS_AVAILABLE:
    # 予測リクエスト総数（status=success/error でラベル分け）
    PREDICT_REQUESTS = Counter(
        "boat_race_predict_requests_total",
        "競艇予測APIの総リクエスト数",
        ["status"],  # success / error / model_not_found
    )

    # 予測処理時間（ヒストグラム）
    PREDICT_LATENCY = Histogram(
        "boat_race_predict_latency_seconds",
        "競艇予測APIの処理時間",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    )

    # 現在ロード中のモデル情報
    MODEL_INFO = Info(
        "boat_race_model",
        "現在の本番モデル情報",
    )

    # モデルがキャッシュにロードされているか
    MODEL_LOADED = Gauge(
        "boat_race_model_loaded",
        "モデルがキャッシュにロードされているか（1=yes, 0=no）",
    )


def record_predict_request(status: str, latency_seconds: float) -> None:
    """
    予測リクエストのメトリクスを記録する

    Args:
        status: "success" / "error" / "model_not_found"
        latency_seconds: 処理時間（秒）
    """
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        PREDICT_REQUESTS.labels(status=status).inc()
        PREDICT_LATENCY.observe(latency_seconds)
    except Exception as e:
        logger.debug(f"メトリクス記録エラー: {e}")


def update_model_info() -> None:
    """本番モデルの情報をメトリクスに反映する"""
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        from app.model.predict import _cached_model
        from app.model.versioning import ModelRegistry

        loaded = _cached_model is not None
        MODEL_LOADED.set(1 if loaded else 0)

        registry = ModelRegistry()
        version = registry.get_production_version() or "unknown"
        MODEL_INFO.info({"version": version})
    except Exception as e:
        logger.debug(f"モデル情報メトリクス更新エラー: {e}")


@router.get("/metrics", summary="Prometheusメトリクス", include_in_schema=False)
async def metrics_endpoint() -> Response:
    """
    Prometheus 形式のメトリクスを返す

    Prometheus の scrape_configs に以下を追加:
      - job_name: boat-race-ai
        static_configs:
          - targets: ['your-host:8000']
        metrics_path: /metrics
    """
    if not _PROMETHEUS_AVAILABLE:
        return PlainTextResponse(
            "# prometheus-client が未インストールです\n",
            status_code=503,
        )

    update_model_info()
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ---- ミドルウェア ----

async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """
    全リクエストにメトリクス計測を付加するミドルウェア
    app.add_middleware() の代わりに app.middleware("http") で登録する

    使い方（main.py）:
        from app.api.metrics import metrics_middleware
        app.middleware("http")(metrics_middleware)
    """
    if not _PROMETHEUS_AVAILABLE or request.url.path == "/metrics":
        return await call_next(request)

    start = time.monotonic()
    try:
        response = await call_next(request)
        latency = time.monotonic() - start

        # /api/v1/predict のみ詳細計測
        if "/predict" in request.url.path:
            status = "success" if response.status_code < 400 else "error"
            record_predict_request(status, latency)

        return response
    except Exception as e:
        latency = time.monotonic() - start
        if "/predict" in request.url.path:
            record_predict_request("error", latency)
        raise
