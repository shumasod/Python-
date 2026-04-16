"""
scripts/convert_data.py のテスト
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# フィクスチャ
# ============================================================

def _make_results_csv(path: Path, n_races: int = 5) -> Path:
    """テスト用レース結果 CSV を生成する（6艇 × n_races レース）"""
    rows = []
    for race_no in range(1, n_races + 1):
        for boat in range(1, 7):
            rows.append({
                "date":        "20260412",
                "jyo_code":    "01",
                "race_no":     race_no,
                "rank":        boat,       # boat 1 が常に1着
                "boat_number": boat,
                "racer_no":    f"R{boat:04d}",
                "racer_name":  f"選手{boat}",
                "time":        "1:50.0",
            })
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return path


def _make_racer_csv(path: Path) -> Path:
    """テスト用選手情報 CSV を生成する"""
    rows = [
        {"racer_no": f"R{i:04d}", "racer_name": f"選手{i}",
         "rank": "A1", "win_rate": 50.0 - i, "2rate": 40.0}
        for i in range(1, 7)
    ]
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return path


@pytest.fixture
def scraped_dir(tmp_path):
    """レース結果 + 選手情報を含む scraped ディレクトリ"""
    d = tmp_path / "scraped"
    _make_results_csv(d / "race_results_20260401_20260412.csv", n_races=10)
    _make_racer_csv(d / "racer_info.csv")
    return d


# ============================================================
# load_race_results
# ============================================================

class TestLoadRaceResults:
    def test_returns_dataframe(self, scraped_dir):
        """DataFrameが返ること"""
        from scripts.convert_data import load_race_results
        df = load_race_results(scraped_dir)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_returns_empty_when_no_files(self, tmp_path):
        """CSVファイルがない場合に空DataFrameを返すこと"""
        from scripts.convert_data import load_race_results
        empty = tmp_path / "empty"
        empty.mkdir()
        df = load_race_results(empty)
        assert df.empty

    def test_merges_multiple_csv_files(self, tmp_path):
        """複数CSVを結合して返すこと"""
        from scripts.convert_data import load_race_results
        d = tmp_path / "multi"
        _make_results_csv(d / "race_results_01.csv", n_races=3)
        _make_results_csv(d / "race_results_02.csv", n_races=4)
        df = load_race_results(d)
        assert len(df) == (3 + 4) * 6  # 各6艇


# ============================================================
# load_racer_info
# ============================================================

class TestLoadRacerInfo:
    def test_returns_dataframe(self, scraped_dir):
        """DataFrameが返ること"""
        from scripts.convert_data import load_racer_info
        df = load_racer_info(scraped_dir)
        assert isinstance(df, pd.DataFrame)
        assert "racer_no" in df.columns

    def test_returns_empty_when_missing(self, tmp_path):
        """racer_info.csv がない場合に空DataFrameを返すこと"""
        from scripts.convert_data import load_racer_info
        empty = tmp_path / "no_racer"
        empty.mkdir()
        df = load_racer_info(empty)
        assert df.empty


# ============================================================
# build_training_rows
# ============================================================

class TestBuildTrainingRows:
    def test_output_has_feature_columns(self, scraped_dir):
        """出力に FEATURE_COLUMNS が含まれること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows
        from app.model.features import FEATURE_COLUMNS

        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"カラム '{col}' が見つかりません"

    def test_output_has_label_column(self, scraped_dir):
        """出力に 'label' カラムが含まれること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows

        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        assert "label" in df.columns

    def test_label_values_in_range(self, scraped_dir):
        """ラベルが 0〜5 の範囲であること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows

        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        assert df["label"].between(0, 5).all()

    def test_row_count_is_6_per_race(self, scraped_dir):
        """1レースあたり6行（6艇分）出力されること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows

        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        assert len(df) % 6 == 0

    def test_empty_results_returns_empty(self):
        """空の results で空DataFrameを返すこと"""
        from scripts.convert_data import build_training_rows

        df = build_training_rows(pd.DataFrame(), pd.DataFrame())
        assert df.empty

    def test_winner_label_is_zero_based(self, scraped_dir):
        """ラベルが1着の艇番-1（0始まり）であること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows

        # フィクスチャでは boat_number=1 が rank=1（1着）
        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        # 全レースで1号艇が1着 → label = 0
        unique_labels = df["label"].unique()
        assert 0 in unique_labels

    def test_racer_win_rate_applied(self, scraped_dir):
        """選手情報から勝率が引き継がれること"""
        from scripts.convert_data import load_race_results, load_racer_info, build_training_rows

        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        # racer_info で win_rate=49.0 (R0001, boat 1)
        assert df["win_rate"].max() > 0


# ============================================================
# _course_win_rate
# ============================================================

class TestCourseWinRate:
    def test_boat1_highest(self):
        """1号艇の枠別勝率が最も高いこと"""
        from scripts.convert_data import _course_win_rate
        assert _course_win_rate(1) > _course_win_rate(6)

    def test_known_values(self):
        """既知の枠別勝率が正しいこと"""
        from scripts.convert_data import _course_win_rate
        assert _course_win_rate(1) == pytest.approx(42.0)
        assert _course_win_rate(6) == pytest.approx(7.5)

    def test_unknown_boat_returns_default(self):
        """存在しない艇番ではデフォルト値を返すこと"""
        from scripts.convert_data import _course_win_rate
        assert _course_win_rate(99) == pytest.approx(10.0)


# ============================================================
# _encode_rank
# ============================================================

class TestEncodeRank:
    def test_a1_is_1(self):
        from scripts.convert_data import _encode_rank
        assert _encode_rank("A1") == 1

    def test_b2_is_4(self):
        from scripts.convert_data import _encode_rank
        assert _encode_rank("B2") == 4

    def test_case_insensitive(self):
        from scripts.convert_data import _encode_rank
        assert _encode_rank("a1") == _encode_rank("A1")

    def test_unknown_returns_b1_default(self):
        from scripts.convert_data import _encode_rank
        assert _encode_rank("X9") == 3  # B1 のデフォルト


# ============================================================
# validate_training_data
# ============================================================

class TestValidateTrainingData:
    def test_valid_data_returns_ok(self, scraped_dir):
        """十分なデータで ok=True を返すこと"""
        from scripts.convert_data import (
            load_race_results, load_racer_info,
            build_training_rows, validate_training_data,
        )
        # 1000レース以上が必要なのでモックで列だけ作る
        from app.model.features import FEATURE_COLUMNS
        import numpy as np

        n = 1000 * 6
        data = {col: np.zeros(n) for col in FEATURE_COLUMNS}
        data["label"] = [i % 6 for i in range(n)]
        data["race_id"] = [f"r{i // 6}" for i in range(n)]
        df = pd.DataFrame(data)

        result = validate_training_data(df)
        assert result["ok"] is True
        assert result["n_races"] == 1000

    def test_empty_data_returns_not_ok(self):
        """空データで ok=False を返すこと"""
        from scripts.convert_data import validate_training_data
        result = validate_training_data(pd.DataFrame())
        assert result["ok"] is False

    def test_small_data_has_issue(self, scraped_dir):
        """レース数が少ない場合に issues に警告が含まれること"""
        from scripts.convert_data import (
            load_race_results, load_racer_info,
            build_training_rows, validate_training_data,
        )
        results = load_race_results(scraped_dir)
        racers  = load_racer_info(scraped_dir)
        df = build_training_rows(results, racers)

        result = validate_training_data(df)
        # 10レースなので "少なすぎます" 警告が出る
        assert any("少なすぎます" in issue for issue in result["issues"])
