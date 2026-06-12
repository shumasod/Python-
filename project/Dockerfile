# ---- ベースイメージ ----
# Python 3.11 slim で軽量化
FROM python:3.11-slim AS base

# タイムゾーン設定（日本時間）
ENV TZ=Asia/Tokyo \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# システム依存パッケージ（LightGBMのビルドに必要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- 依存パッケージインストール ----
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- 本番イメージ ----
FROM dependencies AS production

# アプリコードをコピー
COPY app/ ./app/

# モデルディレクトリを作成（学習済みモデルをマウントするか COPY で追加）
RUN mkdir -p models logs data

# セキュリティ: 非rootユーザーで実行
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# アプリ起動（本番: workers=4, 開発: --reload）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
