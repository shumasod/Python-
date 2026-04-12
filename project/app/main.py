"""
FastAPI アプリケーションエントリーポイント
競艇予想AI APIサーバー
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.predict import router as predict_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router, metrics_middleware
from app.api.feedback import router as feedback_router
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 環境変数フラグ
_USE_DB = os.getenv("USE_DB", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリ起動・終了時の処理
      起動: モデルウォームアップ → DB接続プール初期化 → 起動通知
      終了: DB接続プールのクローズ → 終了通知
    """
    logger.info("競艇予想AIサーバーを起動しています...")

    # ---- モデルウォームアップ ----
    try:
        from app.model.predict import get_model
        get_model()
        logger.info("モデルのウォームアップ完了")
    except FileNotFoundError:
        logger.warning(
            "モデルファイルが見つかりません。"
            "先に scripts/train_model.py を実行してください。"
        )

    # ---- DB接続プール初期化 ----
    if _USE_DB:
        try:
            from app.db import get_pool
            await get_pool()
            logger.info("DB接続プール初期化完了")
        except Exception as e:
            logger.warning(f"DB接続に失敗しました（予測は継続可能）: {e}")

    # ---- 起動通知 ----
    try:
        from app.utils.notification import notify
        await notify("✅ 競艇予想AIサーバーが起動しました")
    except Exception:
        pass  # 通知失敗はサーバー起動に影響させない

    yield  # アプリ稼働中

    # ---- シャットダウン処理 ----
    logger.info("サーバーをシャットダウンしています...")
    if _USE_DB:
        try:
            from app.db import close_pool
            await close_pool()
        except Exception as e:
            logger.warning(f"DB接続クローズエラー: {e}")

    try:
        from app.utils.notification import notify
        await notify("🛑 競艇予想AIサーバーがシャットダウンしました")
    except Exception:
        pass


# ---- FastAPI アプリ初期化 ----
app = FastAPI(
    title="競艇予想AI API",
    description=(
        "LightGBMを使った競艇レース予測APIです。\n\n"
        "## 認証\n"
        "`X-API-Key` ヘッダーに発行済みキーを設定してください。\n\n"
        "## エンドポイント\n"
        "- `POST /api/v1/predict`         : レース予測（1着確率・三連単・推奨買い目）\n"
        "- `POST /api/v1/predict/batch`   : バッチ予測（最大20レース）\n"
        "- `POST /api/v1/result/{id}`     : レース結果を記録（予測精度追跡）\n"
        "- `GET  /api/v1/result/{id}`     : 記録済み結果を取得\n"
        "- `GET  /api/v1/result/summary`  : 的中率サマリー\n"
        "- `GET  /api/v1/stats`           : 予測API利用統計（DB接続時のみ）\n"
        "- `GET  /health`                 : 簡易ヘルスチェック\n"
        "- `GET  /health/detail`          : 詳細ヘルスチェック（DB・モデル状態）\n"
        "- `GET  /metrics`                : Prometheusメトリクス\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---- ミドルウェア ----

# Prometheus 計測ミドルウェア（全リクエスト計測）
@app.middleware("http")
async def _metrics_mw(request: Request, call_next) -> Response:
    return await metrics_middleware(request, call_next)

# CORS（本番では ALLOWED_ORIGINS 環境変数で制限）
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---- ルーター登録 ----
app.include_router(predict_router, prefix="/api/v1", tags=["predict"])
app.include_router(feedback_router, prefix="/api/v1", tags=["feedback"])
app.include_router(health_router, tags=["health"])
app.include_router(metrics_router, tags=["observability"])


@app.get("/health", tags=["health"], include_in_schema=False)
async def health_check() -> dict:
    """ECS / ALB ヘルスチェック用（常時200）"""
    return {"status": "ok", "service": "boat-race-ai"}
