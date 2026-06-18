"""
scripts/auto_retrain.py のテスト

各関数をモンキーパッチして、ドリフト判定 → 学習 → 昇格 → 通知の
パイプラインフローを検証する。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_versioning import _PicklableModel


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def registry_env(tmp_path, monkeypatch):
    """テスト用 ModelRegistry 環境を構築して返す"""
    import app.model.versioning as ver_mod
    monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
    return tmp_path


@pytest.fixture
def train_env(registry_env, monkeypatch):
    """学習パイプライン全体を tmp_path に向けてセットアップ"""
    import app.model.train as train_mod
    monkeypatch.setattr(train_mod, "MODEL_DIR", registry_env)
    return registry_env


# ============================================================
# check_drift
# ============================================================

class TestCheckDrift:
    def _make_report(self, needs_retrain: bool, n_alerts: int = 0):
        """DriftReport の簡易モックを作る"""
        result = MagicMock()
        result.needs_retraining = needs_retrain
        feat = MagicMock()
        feat.status = "alert" if n_alerts else "stable"
        result.feature_results = [feat] * (n_alerts or 3)
        return result

    def test_no_drift_returns_false(self, monkeypatch):
        """ドリフトなしのとき (False, dict) を返すこと"""
        from scripts.auto_retrain import check_drift
        report = self._make_report(needs_retrain=False, n_alerts=0)
        with patch("scripts.auto_retrain.DriftDetector") as MockDD:
            instance = MockDD.return_value
            instance.check.return_value = report
            result, info = check_drift(data_path=None, n_races=100)
        assert result is False
        assert info["needs_retraining"] is False
        assert info["n_alerts"] == 0

    def test_drift_detected_returns_true(self, monkeypatch):
        """ドリフト検知時に (True, dict) を返すこと"""
        from scripts.auto_retrain import check_drift
        report = self._make_report(needs_retrain=True, n_alerts=3)
        with patch("scripts.auto_retrain.DriftDetector") as MockDD:
            instance = MockDD.return_value
            instance.check.return_value = report
            result, info = check_drift(data_path=None, n_races=100)
        assert result is True
        assert info["n_alerts"] == 3

    def test_n_features_in_info(self, monkeypatch):
        """info に n_features が含まれること"""
        from scripts.auto_retrain import check_drift
        report = self._make_report(needs_retrain=False, n_alerts=0)
        report.feature_results = [MagicMock(status="stable")] * 12
        with patch("scripts.auto_retrain.DriftDetector") as MockDD:
            instance = MockDD.return_value
            instance.check.return_value = report
            _, info = check_drift(data_path=None, n_races=100)
        assert info["n_features"] == 12


# ============================================================
# run_training
# ============================================================

class TestRunTraining:
    def test_returns_version_and_metrics(self, train_env):
        """(version_name, metrics_dict) を返すこと"""
        from scripts.auto_retrain import run_training
        version, metrics = run_training(
            data_path=None, n_races=200, n_splits=2, notes="テスト"
        )
        assert isinstance(version, str)
        assert "boat_race_model" in version
        assert "cv_logloss_mean" in metrics

    def test_registers_in_registry(self, train_env):
        """学習後にレジストリへ登録されること"""
        from scripts.auto_retrain import run_training
        from app.model.versioning import ModelRegistry
        run_training(data_path=None, n_races=200, n_splits=2, notes="")
        reg = ModelRegistry()
        assert len(reg.list_versions()) >= 1

    def test_notes_saved(self, train_env):
        """notes がバージョンのメタデータに保存されること"""
        from scripts.auto_retrain import run_training
        from app.model.versioning import ModelRegistry
        version, _ = run_training(
            data_path=None, n_races=200, n_splits=2, notes="ドリフト検知による再学習"
        )
        reg = ModelRegistry()
        versions = reg.list_versions()
        target = next(v for v in versions if v["version"] == version)
        assert "ドリフト" in target.get("notes", "")


# ============================================================
# promote_version
# ============================================================

class TestPromoteVersion:
    def test_promotes_registered_version(self, registry_env):
        """登録済みバージョンを本番昇格できること"""
        from app.model.versioning import ModelRegistry
        from scripts.auto_retrain import promote_version

        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 500, "feature_columns": ["x"] * 12,
        }
        version = registry.register(_PicklableModel(), metrics)
        promote_version(version)

        reg2 = ModelRegistry()
        assert reg2.get_production_version() == version

    def test_nonexistent_version_raises(self, registry_env):
        """存在しないバージョンでは FileNotFoundError が発生すること"""
        from scripts.auto_retrain import promote_version
        with pytest.raises(FileNotFoundError):
            promote_version("boat_race_model_v99999999_99")


# ============================================================
# main() フロー
# ============================================================

class TestMainFlow:
    """main() フローのテスト。patch はモジュール属性を直接置き換え、main() を呼ぶ。"""

    def test_no_drift_no_force_skips_training(self, train_env, monkeypatch, capsys):
        """ドリフトなし & --force なしで再学習をスキップすること"""
        import scripts.auto_retrain as ar
        monkeypatch.setattr(sys, "argv", [
            "auto_retrain.py", "--no-notify", "--n-races", "100"
        ])
        monkeypatch.setattr(ar, "check_drift", lambda *a, **k: (
            False, {"needs_retraining": False, "n_alerts": 0, "n_features": 3}
        ))
        mock_train = MagicMock()
        monkeypatch.setattr(ar, "run_training", mock_train)

        ar.main()

        mock_train.assert_not_called()
        out = capsys.readouterr().out
        assert "スキップ" in out

    def test_force_runs_training(self, train_env, monkeypatch):
        """--force でドリフトなしでも学習が実行されること"""
        import scripts.auto_retrain as ar
        monkeypatch.setattr(sys, "argv", [
            "auto_retrain.py", "--force", "--no-notify",
            "--n-races", "200", "--n-splits", "2",
        ])
        monkeypatch.setattr(ar, "check_drift", lambda *a, **k: (
            False, {"needs_retraining": False, "n_alerts": 0, "n_features": 3}
        ))
        mock_train = MagicMock(return_value=("boat_race_model_v_test", {"cv_logloss_mean": 1.5}))
        mock_promote = MagicMock()
        monkeypatch.setattr(ar, "run_training", mock_train)
        monkeypatch.setattr(ar, "promote_version", mock_promote)

        ar.main()

        mock_train.assert_called_once()
        mock_promote.assert_not_called()  # --auto-promote 未指定

    def test_auto_promote_calls_promote(self, train_env, monkeypatch):
        """--auto-promote で promote_version が呼ばれること"""
        import scripts.auto_retrain as ar
        monkeypatch.setattr(sys, "argv", [
            "auto_retrain.py", "--force", "--auto-promote", "--no-notify",
            "--n-races", "200", "--n-splits", "2",
        ])
        monkeypatch.setattr(ar, "check_drift", lambda *a, **k: (
            True, {"needs_retraining": True, "n_alerts": 2, "n_features": 3}
        ))
        monkeypatch.setattr(ar, "run_training", MagicMock(
            return_value=("boat_race_model_v_test", {"cv_logloss_mean": 1.5})
        ))
        mock_promote = MagicMock()
        monkeypatch.setattr(ar, "promote_version", mock_promote)

        ar.main()

        mock_promote.assert_called_once_with("boat_race_model_v_test")

    def test_drift_triggers_training(self, train_env, monkeypatch):
        """ドリフト検知時は --force なしでも学習が実行されること"""
        import scripts.auto_retrain as ar
        monkeypatch.setattr(sys, "argv", [
            "auto_retrain.py", "--no-notify",
            "--n-races", "200", "--n-splits", "2",
        ])
        monkeypatch.setattr(ar, "check_drift", lambda *a, **k: (
            True, {"needs_retraining": True, "n_alerts": 3, "n_features": 3}
        ))
        mock_train = MagicMock(return_value=("boat_race_model_v_test", {"cv_logloss_mean": 1.5}))
        monkeypatch.setattr(ar, "run_training", mock_train)
        monkeypatch.setattr(ar, "promote_version", MagicMock())

        ar.main()

        mock_train.assert_called_once()


# ============================================================
# _send_notification
# ============================================================

class TestSendNotification:
    def test_swallows_exception(self):
        """通知失敗は例外を伝播させないこと"""
        from scripts.auto_retrain import _send_notification
        with patch(
            "scripts.auto_retrain.notify_sync",
            side_effect=RuntimeError("接続エラー"),
        ):
            _send_notification("v1", {}, {"needs_retraining": False, "n_alerts": 0})

    def test_calls_notify_sync(self):
        """notify_sync が呼ばれること"""
        from scripts.auto_retrain import _send_notification
        with patch("scripts.auto_retrain.notify_sync") as mock_notify:
            _send_notification(
                "boat_race_model_v20260420_1",
                {"cv_logloss_mean": 1.5, "cv_accuracy_mean": 0.28, "n_samples": 1000},
                {"needs_retraining": True, "n_alerts": 2},
            )
        mock_notify.assert_called_once()
        msg = mock_notify.call_args.args[0]
        assert "boat_race_model_v20260420_1" in msg
