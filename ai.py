# main.py
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
import asyncio
import json
import time
import hashlib
import jwt
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging
import base64

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# データモデル
class User(BaseModel):
    id: Optional[str] = None
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    created_at: Optional[datetime] = None

class AIRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    model: str = Field(default="gpt-3.5-turbo")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class AIResponse(BaseModel):
    response: str
    tokens_used: int
    processing_time: float
    model: str

class ImageAnalysisRequest(BaseModel):
    image_base64: str
    analysis_type: str = Field(default="general")

    @validator("analysis_type")
    def validate_analysis_type(cls, v):
        allowed_types = ["general", "objects", "text", "faces"]
        if v not in allowed_types:
            raise ValueError(f"analysis_type must be one of {allowed_types}")
        return v

class RealTimeMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

# Redis接続 (実際の使用時はRedisサーバーが必要)
class MockRedis:
    def __init__(self):
        self.data: Dict[str, Any] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self.data[key] = value
        return True

    async def delete(self, key: str):
        if key in self.data:
            del self.data[key]
        return True

redis_client = MockRedis()

# WebSocket接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id in self.user_connections:
            del self.user_connections[user_id]
        logger.info(f"User {user_id} disconnected")

    async def send_personal_message(self, message: str, user_id: str):
        ws = self.user_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                disconnected.append(connection)

        # 切断されたコネクションを削除
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

# アプリケーション初期化
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    logger.info("🚀 ハイテクAPI起動中…")
    await redis_client.set("startup_time", datetime.utcnow().isoformat())
    yield
    # 終了時の処理
    logger.info("⚡ ハイテクAPI終了")

app = FastAPI(
    title="🔮 ハイテクAI API",
    description="最新技術を統合したモダンなAPIプラットフォーム",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ミドルウェア設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# セキュリティ
security = HTTPBearer()
SECRET_KEY = "your-super-secret-key-change-in-production"

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# レート制限
async def rate_limit(user_id: str, limit: int = 100, window: int = 3600):
    key = f"rate_limit:{user_id}"
    current = await redis_client.get(key)
    if current and int(current) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    count = int(current) + 1 if current else 1
    await redis_client.set(key, str(count), ex=window)
    return True

# バックグラウンドタスク関数
async def log_ai_usage(user_id: str, model: str, tokens: int):
    """AI使用ログをバックグラウンドで記録"""
    log_data = {
        "user_id": user_id,
        "model": model,
        "tokens": tokens,
        "timestamp": datetime.utcnow().isoformat()
    }
    await redis_client.set(f"ai_log:{uuid.uuid4()}", json.dumps(log_data))
    logger.info(f"AI usage logged for user {user_id}")

# エンドポイント
@app.get("/")
async def root():
    """ルートエンドポイント - システム情報を返す"""
    startup_time = await redis_client.get("startup_time")
    return {
        "message": "🔮 ハイテクAI APIへようこそ",
        "version": "2.0.0",
        "features": [
            "AI統合",
            "リアルタイム通信",
            "画像分析",
            "認証システム",
            "レート制限",
            "バックグラウンドタスク"
        ],
        "startup_time": startup_time,
        "status": "operational"
    }

@app.post("/auth/register")
async def register_user(user: User):
    """ユーザー登録"""
    user.id = str(uuid.uuid4())
    user.created_at = datetime.utcnow()

    # 実際の実装では、ここでデータベースに保存
    await redis_client.set(f"user:{user.id}", user.json())

    token = create_jwt_token(user.id)
    return {
        "user": user,
        "token": token,
        "message": "ユーザー登録完了"
    }

@app.post("/ai/chat", response_model=AIResponse)
async def ai_chat(
    request: AIRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_token)
):
    """AI チャット機能"""
    await rate_limit(user_id, limit=50, window=3600)

    start_time = time.time()

    # 実際の実装では、OpenAI APIやその他のAIサービスを呼び出し
    # ここではモックレスポンスを生成
    mock_response = f"AIからの応答: {request.prompt}について考えてみました。これは{request.model}モデルによる回答です。"

    processing_time = time.time() - start_time

    response = AIResponse(
        response=mock_response,
        tokens_used=len(mock_response.split()),
        processing_time=processing_time,
        model=request.model
    )

    # ログをバックグラウンドで記録
    background_tasks.add_task(log_ai_usage, user_id, request.model, response.tokens_used)

    return response

@app.post("/ai/image-analysis")
async def analyze_image(
    request: ImageAnalysisRequest,
    user_id: str = Depends(verify_token)
):
    """画像分析機能"""
    await rate_limit(user_id, limit=20, window=3600)

    try:
        # Base64デコード（実際の実装では画像を処理）
        image_data = base64.b64decode(request.image_base64)

        # モック分析結果
        analysis_results = {
            "general": ["画像", "デジタル", "データ"],
            "objects": ["コンピューター", "スクリーン"],
            "text": "検出されたテキストなし",
            "faces": 0
        }

        return {
            "analysis_type": request.analysis_type,
            "results": analysis_results.get(request.analysis_type),
            "confidence": 0.95,
            "processing_time": 0.234
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"画像分析エラー: {str(e)}")

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocketリアルタイム通信"""
    await manager.connect(websocket, user_id)

    # 接続確認メッセージ
    await websocket.send_text(json.dumps({
        "type": "connection_confirmed",
        "message": f"ユーザー {user_id} がリアルタイム通信に接続しました",
        "timestamp": datetime.utcnow().isoformat()
    }))

    try:
        while True:
            # クライアントからのメッセージを受信
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                continue

            # メッセージタイプに応じて処理
            if message_data.get("type") == "broadcast":
                await manager.broadcast(json.dumps({
                    "type": "broadcast",
                    "from": user_id,
                    "message": mes
