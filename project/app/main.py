"""
FastAPI アプリケーションエントリーポイント
競艇予想AI APIサーバー
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.predict import router as predict_router
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリ起動時にモデルをウォームアップする
    （初回リクエストのレイテンシを防ぐ）
    """
    logger.info("競艇予想AIサーバーを起動しています...")
    try:
        # モデルキャッシュを事前にロード
        from app.model.predict import get_model
        get_model()
        logger.info("モデルのウォームアップ完了")
    except FileNotFoundError:
        logger.warning(
            "モデルファイルが見つかりません。"
            "先に scripts/train_model.py を実行してください。"
        )
    yield
    logger.info("サーバーをシャットダウンしています...")


# FastAPI アプリケーション初期化
app = FastAPI(
    title="競艇予想AI API",
    description=(
        "LightGBMを使った競艇レース予測APIです。\n\n"
        "## 機能\n"
        "- 各艇の1着確率予測\n"
        "- 三連単確率計算\n"
        "- ケリー基準による買い目推奨\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定（開発環境用：本番では特定オリジンに制限すること）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(predict_router, prefix="/api/v1", tags=["predict"])


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """ヘルスチェックエンドポイント"""
    return {"status": "ok", "service": "boat-race-ai"}
