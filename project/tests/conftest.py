"""
pytest 共通フィクスチャ・設定
"""
import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def trained_model(tmp_path_factory, monkeypatch_session):
    """
    セッションスコープ: 一度だけ小規模なモデルを学習して返す
    複数テストファイルで共用できる
    """
    import app.model.train as train_module
    from app.model.features import generate_sample_training_data, preprocess_dataframe
    from app.model.train import train_model

    tmp_dir = tmp_path_factory.mktemp("models")
    monkeypatch_session.setattr(train_module, "MODEL_DIR", tmp_dir)

    df = preprocess_dataframe(generate_sample_training_data(n_races=200))
    model, metrics = train_model(df, model_name="test_model", n_splits=2)
    return model, metrics, tmp_dir


@pytest.fixture(scope="session")
def monkeypatch_session(request):
    """session スコープで使える monkeypatch"""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session")
def sample_race_features():
    """セッションスコープ: テスト用の特徴量 DataFrame shape=(6, 12)"""
    import numpy as np
    import pandas as pd
    from app.model.features import FEATURE_COLUMNS
    data = np.random.default_rng(42).random((6, len(FEATURE_COLUMNS)))
    return pd.DataFrame(data, columns=FEATURE_COLUMNS)
