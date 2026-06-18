"""
特徴量モジュールのユニットテスト
"""
import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.features import (
    build_features,
    preprocess_dataframe,
    generate_sample_training_data,
    FEATURE_COLUMNS,
    _encode_weather,
    _encode_rank,
)


# ---- フィクスチャ ----

@pytest.fixture
def valid_race_data():
    """正常系レースデータ"""
    return {
        "race_id": "test_001",
        "boats": [
            {
                "boat_number": i,
                "racer_rank": "A1",
                "win_rate": 20.0 + i,
                "motor_score": 55.0,
                "course_win_rate": 30.0 - i * 2,
                "start_timing": 0.15 + i * 0.01,
                "motor_2rate": 40.0,
                "boat_2rate": 38.0,
                "recent_3_avg": 3.0 + i * 0.2,
            }
            for i in range(1, 7)
        ],
        "weather": {"condition": "晴", "wind_speed": 2.5, "water_temp": 22.0},
    }


# ---- build_features テスト ----

class TestBuildFeatures:
    def test_shape(self, valid_race_data):
        """6×n_features の DataFrame が返ることを確認"""
        df = build_features(valid_race_data)
        assert df.shape == (6, len(FEATURE_COLUMNS))

    def test_column_names(self, valid_race_data):
        """全カラムが揃っていることを確認"""
        df = build_features(valid_race_data)
        assert list(df.columns) == FEATURE_COLUMNS

    def test_boat_count_error(self):
        """6艇以外でエラーになることを確認"""
        with pytest.raises(ValueError, match="6艇必要"):
            build_features({"boats": [{"boat_number": 1}]})

    def test_weather_code(self, valid_race_data):
        """天候コードが正しくエンコードされることを確認"""
        df = build_features(valid_race_data)
        assert df["weather_code"].iloc[0] == 0  # 晴 = 0

    def test_wind_speed(self, valid_race_data):
        """風速が正しく設定されることを確認"""
        df = build_features(valid_race_data)
        assert df["wind_speed"].iloc[0] == pytest.approx(2.5)

    def test_no_nan(self, valid_race_data):
        """欠損値がないことを確認"""
        df = build_features(valid_race_data)
        assert not df.isnull().any().any()


# ---- encode 関数テスト ----

class TestEncoders:
    @pytest.mark.parametrize("condition,expected", [
        ("晴", 0),
        ("曇", 1),
        ("雨", 2),
        ("unknown", 0),  # デフォルト
    ])
    def test_encode_weather(self, condition, expected):
        assert _encode_weather(condition) == expected

    @pytest.mark.parametrize("rank,expected", [
        ("A1", 1), ("A2", 2), ("B1", 3), ("B2", 4),
        ("a1", 1),  # 大文字小文字無関係
        ("XX", 3),  # 不明ランクはB1扱い
    ])
    def test_encode_rank(self, rank, expected):
        assert _encode_rank(rank) == expected


# ---- preprocess_dataframe テスト ----

class TestPreprocessDataframe:
    def test_nan_fill(self):
        """欠損値が中央値で補完されることを確認"""
        df = generate_sample_training_data(n_races=10)
        df.loc[0, "win_rate"] = np.nan
        processed = preprocess_dataframe(df)
        assert not processed["win_rate"].isnull().any()

    def test_start_timing_clip(self):
        """スタートタイミングが0〜1にクリッピングされることを確認"""
        df = generate_sample_training_data(n_races=5)
        df["start_timing"] = 999.0  # 異常値
        processed = preprocess_dataframe(df)
        assert processed["start_timing"].max() <= 1.0

    def test_win_rate_scale(self):
        """0〜1スケールの勝率が100倍されることを確認"""
        df = generate_sample_training_data(n_races=5)
        df["win_rate"] = 0.25  # 0〜1スケール
        processed = preprocess_dataframe(df)
        assert processed["win_rate"].max() <= 100.0


# ---- generate_sample_training_data テスト ----

class TestGenerateSampleData:
    def test_row_count(self):
        """n_races × 6 行生成されることを確認"""
        df = generate_sample_training_data(n_races=100)
        assert len(df) == 100 * 6

    def test_label_range(self):
        """ラベルが 0〜5 の範囲であることを確認"""
        df = generate_sample_training_data(n_races=50)
        assert df["label"].between(0, 5).all()

    def test_boat_number_range(self):
        """艇番が 1〜6 の範囲であることを確認"""
        df = generate_sample_training_data(n_races=50)
        assert df["boat_number"].between(1, 6).all()
