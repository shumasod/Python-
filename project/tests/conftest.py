"""
pytest 共通フィクスチャ・設定
"""
import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
