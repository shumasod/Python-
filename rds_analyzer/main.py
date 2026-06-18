"""
RDS Cost & Performance Analyzer - FastAPI メインアプリケーション

設計意図:
- FastAPI による高性能な非同期 REST API
- OpenAPI (Swagger UI) でのドキュメント自動生成
- CORS 設定でフロントエンド（React）からのアクセスを許可
- 構造化ログ（JSON形式）でオブザーバビリティを確保

起動方法:
    uvicorn rds_analyzer.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api.routes import router

# ============================================================
# 構造化ログ設定
# ============================================================

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)


# ============================================================
# アプリケーションライフサイクル
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """アプリ起動/終了時の処理"""
    logger.info("RDS Analyzer 起動", version=__version__)
    yield
    logger.info("RDS Analyzer 終了")


# ============================================================
# FastAPI アプリケーション
# ============================================================

app = FastAPI(
    title="RDS Cost & Performance Analyzer",
    description=(
        "Amazon RDS のコスト見積もりとパフォーマンス改善分析を行う REST API\n\n"
        "## 主な機能\n"
        "- **コスト分析**: 月次コスト算出・内訳表示・異常検知\n"
        "- **パフォーマンス分析**: CPU/メモリ/IO/コネクションのボトルネック検知\n"
        "- **改善提案**: 優先度付き改善提案（コスト削減・パフォーマンス向上）\n"
        "- **スコアリング**: コスト効率スコア・パフォーマンス健全性スコア（0〜100）\n\n"
        "⚠️ **注意**: コスト計算は推定値です。実際の請求額は AWS Console でご確認ください。"
    ),
    version=__version__,
    contact={
        "name": "AWS Architect / SRE Team",
    },
    lifespan=lifespan,
)

# ============================================================
# ミドルウェア
# ============================================================

# CORS（React フロントエンドからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React 開発サーバー
        "http://localhost:5173",   # Vite 開発サーバー
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip 圧縮（1KB 以上のレスポンスを圧縮）
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ============================================================
# リクエストログ・レイテンシ計測ミドルウェア
# ============================================================

@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """全リクエストのログとレイテンシ計測"""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "HTTP リクエスト",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )

    # レスポンスヘッダーにレイテンシを追加（デバッグ用）
    response.headers["X-Process-Time-Ms"] = str(round(duration_ms, 2))
    return response


# ============================================================
# グローバル例外ハンドラー
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未処理例外をキャッチして 500 を返す"""
    logger.error(
        "未処理例外",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "内部サーバーエラーが発生しました"},
    )


# ============================================================
# ルーター登録
# ============================================================

app.include_router(router, prefix="/api/v1")


# ============================================================
# ルートエンドポイント（リダイレクト）
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    """ルートを API ドキュメントにリダイレクト"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
