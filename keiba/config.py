# config.py
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class Config:
    """アプリケーション設定クラス
    
    属性:
        BASE_URL: スクレイピング対象のベースURL
        NUM_PAGES: スクレイピングするページ数
        DEBUG: デバッグモードフラグ
        MODEL_PATH: 事前トレーニング済みモデルのパス（Noneの場合は新規トレーニング）
        LOG_LEVEL: ロギングレベル
    """
    BASE_URL: str = field(default_factory=lambda: os.environ.get('JRA_BASE_URL', 'https://example.com/jra'))
    NUM_PAGES: int = field(default_factory=lambda: int(os.environ.get('JRA_NUM_PAGES', '5')))
    DEBUG: bool = field(default_factory=lambda: os.environ.get('JRA_DEBUG', 'False').lower() == 'true')
    MODEL_PATH: Optional[str] = field(default_factory=lambda: os.environ.get('JRA_MODEL_PATH'))
    LOG_LEVEL: str = field(default_factory=lambda: os.environ.get('JRA_LOG_LEVEL', 'INFO'))
    
    def __post_init__(self):
        """設定値の型変換と検証を行う"""
        if isinstance(self.NUM_PAGES, str):
            self.NUM_PAGES = int(self.NUM_PAGES)
        
        # モデルパスが指定されている場合はディレクトリを作成
        if self.MODEL_PATH:
            model_dir = os.path.dirname(self.MODEL_PATH)
            if model_dir and not os.path.exists(model_dir):
                os.makedirs(model_dir)
