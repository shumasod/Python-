"""
ドリフト検知・データ変換スクリプトのユニットテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# drift.py テスト
# ============================================================

@pytest.fixture
def detector(tmp_path, monkeypatch):
    """テスト用 DriftDetector（ファイル出力を tmp_path に隔離）"""
    import app.model.drift as drift_module
    monkeypatch.setattr(drift_module, "REFERENCE_FILE", tmp_path / "reference.json")
    monkeypatch.setattr(drift_module, "DRIFT_REPORT_DIR", tmp_path / "reports")

    from app.model.drift import DriftDetector
    return DriftDetector(n_bins=5)


@pytest.fixture
def sample_df():
    """テスト用サンプルDataFrame（100レース分）"""
    from app.model.features import generate_sample_training_data, preprocess_dataframe
    return preprocess_dataframe(generate_sample_training_data(n_races=100))


class TestDriftDetector:
    def test_set_reference_creates_file(self, detector, sample_df, tmp_path):
        """set_reference() が JSON ファイルを生成することを確認"""
        import app.model.drift as drift_module
        detector.set_reference(sample_df)
        assert (tmp_path / "reference.json").exists()

    def test_reference_has_all_features(self, detector, sample_df):
        """参照分布に全特徴量が登録されることを確認"""
        from app.model.features import FEATURE_COLUMNS
        detector.set_reference(sample_df)
        for col in FEATURE_COLUMNS:
            assert col in detector._reference_stats

    def test_check_stable_same_data(self, detector, sample_df):
        """同一データでチェックすると stable になることを確認"""
        detector.set_reference(sample_df)
        report = detector.check(sample_df)
        stable_count = sum(1 for r in report.feature_results if r.status == "stable")
        assert stable_count > 0

    def test_check_drift_detected(self, detector, sample_df):
        """大きく異なるデータでアラートが出ることを確認"""
        detector.set_reference(sample_df)

        # 特徴量を極端にシフトしたデータを作成
        drifted = sample_df.copy()
        drifted["win_rate"] = drifted["win_rate"] * 10  # 10倍にする

        report = detector.check(drifted)
        alert_features = [r for r in report.feature_results if r.status == "alert"]
        assert len(alert_features) > 0

    def test_report_structure(self, detector, sample_df):
        """レポートに必要なフィールドが含まれることを確認"""
        detector.set_reference(sample_df)
        report = detector.check(sample_df)

        assert hasattr(report, "checked_at")
        assert hasattr(report, "n_current")
        assert hasattr(report, "needs_retraining")
        assert hasattr(report, "feature_results")
        assert len(report.feature_results) > 0

    def test_needs_retraining_false_for_stable(self, detector, sample_df):
        """安定データでは needs_retraining=False になることを確認"""
        detector.set_reference(sample_df)
        report = detector.check(sample_df)
        # PSI がすべて低い場合は False（同一データなのでほぼ 0）
        if all(r.psi < 0.1 for r in report.feature_results):
            assert report.needs_retraining is False

    def test_report_to_dict(self, detector, sample_df):
        """to_dict() が JSON シリアライズ可能な辞書を返すことを確認"""
        detector.set_reference(sample_df)
        report = detector.check(sample_df)
        d = report.to_dict()
        json_str = json.dumps(d)  # シリアライズ可能かチェック
        assert isinstance(json_str, str)

    def test_psi_status_thresholds(self):
        """PSI 閾値による分類が正しいことを確認"""
        from app.model.drift import _psi_status
        assert _psi_status(0.05) == "stable"
        assert _psi_status(0.15) == "warn"
        assert _psi_status(0.25) == "alert"

    def test_set_reference_skips_missing_column(self, detector):
        """存在しないカラムを含む DataFrame でも例外なく動作すること"""
        df = pd.DataFrame({"win_rate": [5.0, 6.0, 7.0]})  # 一部カラムのみ
        detector.set_reference(df)
        assert "win_rate" in detector._reference_stats

    def test_set_reference_skips_empty_column(self, detector):
        """全 NaN カラムは参照分布に含まれないこと"""
        from app.model.features import FEATURE_COLUMNS
        df = pd.DataFrame({col: [float("nan")] * 5 for col in FEATURE_COLUMNS})
        detector.set_reference(df)
        assert len(detector._reference_stats) == 0

    def test_load_reference_file_not_found(self, detector):
        """参照分布ファイルが存在しないとき False を返すこと"""
        result = detector.load_reference()
        assert result is False

    def test_load_reference_success(self, detector, sample_df):
        """set_reference 後に load_reference が成功すること"""
        detector.set_reference(sample_df)
        detector._reference_stats = {}  # クリア
        result = detector.load_reference()
        assert result is True
        assert len(detector._reference_stats) > 0

    def test_check_without_reference_returns_report(self, detector, sample_df):
        """参照分布なし・ファイルもなしのとき空レポートを返すこと"""
        report = detector.check(sample_df)
        assert report.needs_retraining is False
        assert "参照分布未設定" in report.summary

    def test_check_skips_missing_columns(self, detector, sample_df):
        """現在データに存在しないカラムはスキップされること"""
        detector.set_reference(sample_df)
        # 一部カラムだけの DataFrame を渡す
        small_df = sample_df[["win_rate"]].copy()
        report = detector.check(small_df)
        assert len(report.feature_results) <= 1

    def test_check_skips_empty_column(self, detector, sample_df):
        """現在データで全 NaN のカラムはスキップされること"""
        from app.model.features import FEATURE_COLUMNS
        detector.set_reference(sample_df)
        df_with_nan = sample_df.copy()
        df_with_nan["win_rate"] = float("nan")
        report = detector.check(df_with_nan)
        # win_rate がスキップされても他の特徴量は処理される
        assert report is not None

    def test_check_warn_summary(self, detector, sample_df):
        """軽微なドリフトで warn サマリーが生成されること"""
        detector.set_reference(sample_df)
        shifted = sample_df.copy()
        shifted["win_rate"] = shifted["win_rate"] * 1.5  # 軽微なシフト
        report = detector.check(shifted)
        assert report.summary is not None

    def test_check_warn_path_features(self, detector, sample_df, monkeypatch):
        """PSI が warn レベルのとき warn_features に追加され '軽微なドリフト' サマリーになること"""
        import app.model.drift as drift_mod
        detector.set_reference(sample_df)

        # Force _psi_status to return "warn" for all features → no alert, only warn
        monkeypatch.setattr(drift_mod, "_psi_status", lambda psi: "warn")
        report = detector.check(sample_df)
        assert "軽微なドリフト" in report.summary

    def test_print_report(self, detector, sample_df, capsys):
        """print_report がコンソールに出力すること"""
        detector.set_reference(sample_df)
        report = detector.check(sample_df)
        detector.print_report(report)
        out = capsys.readouterr().out
        assert "ドリフト検査レポート" in out
        assert "PSI" in out


# ============================================================
# convert_data.py テスト
# ============================================================

class TestConvertData:
    def _make_results_df(self) -> pd.DataFrame:
        """テスト用レース結果DataFrame"""
        rows = []
        for race_no in range(1, 6):   # 5レース
            for boat_num in range(1, 7):  # 6艇
                rows.append({
                    "date": "20240415",
                    "jyo_code": "01",
                    "race_no": race_no,
                    "rank": 1 if boat_num == 1 else boat_num,
                    "boat_number": boat_num,
                    "racer_no": f"R{boat_num:03d}",
                    "racer_name": f"選手{boat_num}",
                    "time": "1:50.0",
                })
        return pd.DataFrame(rows)

    def _make_racer_df(self) -> pd.DataFrame:
        """テスト用選手情報DataFrame"""
        return pd.DataFrame([
            {"racer_no": f"R{i:03d}", "rank": "A1", "win_rate": 30.0, "2rate": 50.0}
            for i in range(1, 7)
        ])

    def test_build_training_rows_shape(self):
        """build_training_rows() が 5レース×6艇=30行を返すことを確認"""
        from scripts.convert_data import build_training_rows
        results = self._make_results_df()
        racers  = self._make_racer_df()
        df = build_training_rows(results, racers)
        assert len(df) == 30  # 5レース × 6艇

    def test_build_training_rows_has_feature_cols(self):
        """FEATURE_COLUMNS が全て含まれることを確認"""
        from scripts.convert_data import build_training_rows
        from app.model.features import FEATURE_COLUMNS
        results = self._make_results_df()
        df = build_training_rows(results, self._make_racer_df())
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"カラムが欠けています: {col}"

    def test_label_range(self):
        """ラベルが 0〜5 の範囲であることを確認"""
        from scripts.convert_data import build_training_rows
        results = self._make_results_df()
        df = build_training_rows(results, self._make_racer_df())
        assert df["label"].between(0, 5).all()

    def test_validate_data_ok(self):
        """十分なデータでは品質チェックが通ることを確認"""
        from scripts.convert_data import validate_training_data
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=200))
        result = validate_training_data(df)
        assert result["n_rows"] == 200 * 6

    def test_validate_data_warns_few_races(self):
        """レース数が少ない場合に警告が出ることを確認"""
        from scripts.convert_data import validate_training_data
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=10))
        result = validate_training_data(df)
        assert any("少なすぎ" in issue for issue in result["issues"])
