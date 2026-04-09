"""
FastAPI アプリケーションエントリーポイント
競艇予想AI APIサーバー
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.predict import router as predict_router
from app.utils.logger import get_logger

logger = get_logger(__name__)

# DB統合は環境変数で制御（asyncpg 未インストール環境でも動作させる）
_USE_DB = os.getenv("USE_DB", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリ起動・終了時の処理
      起動: モデルウォームアップ + DB接続プール初期化
      終了: DB接続プールのクローズ
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

    yield  # アプリ稼働中

    # ---- シャットダウン処理 ----
    logger.info("サーバーをシャットダウンしています...")
    if _USE_DB:
        try:
            from app.db import close_pool
            await close_pool()
        except Exception as e:
            logger.warning(f"DB接続クローズエラー: {e}")


# FastAPI アプリケーション初期化
app = FastAPI(
    title="競艇予想AI API",
    description=(
        "LightGBMを使った競艇レース予測APIです。\n\n"
        "## エンドポイント\n"
        "- `POST /api/v1/predict` : レース予測（1着確率・三連単・推奨買い目）\n"
        "- `GET  /api/v1/stats`   : 予測API利用統計（DB接続時のみ）\n"
        "- `GET  /health`         : 簡易ヘルスチェック\n"
        "- `GET  /health/detail`  : 詳細ヘルスチェック（DB・モデル状態）\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定（本番では ALLOWED_ORIGINS 環境変数で制限すること）
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(predict_router, prefix="/api/v1", tags=["predict"])

# ヘルスチェックルーター（詳細版）
from app.api.health import router as health_router
app.include_router(health_router, tags=["health"])


@app.get("/health", tags=["health"], include_in_schema=False)
async def health_check() -> dict:
    """ECS ヘルスチェック用シンプルエンドポイント（常時200を返す）"""
    return {"status": "ok", "service": "boat-race-ai"}
