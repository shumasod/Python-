"""
scripts/train_model.py のテスト

parse_args と main() の各フローを検証する。
実際の学習は重いので、run_training 相当の関数を monkeypatch して
CLI フローのみに絞る。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# parse_args
# ============================================================

class TestParseArgs:
    def test_defaults(self, monkeypatch):
        """デフォルト引数が正しいこと"""
        monkeypatch.setattr(sys, "argv", ["train_model.py"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.use_sample is False
        assert args.data_path is None
        assert args.n_races == 2000
        assert args.model_name == "boat_race_model"
        assert args.n_splits == 5
        assert args.auto_promote is False
        assert args.notes == ""

    def test_use_sample_flag(self, monkeypatch):
        """--use-sample フラグが True になること"""
        monkeypatch.setattr(sys, "argv", ["train_model.py", "--use-sample"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.use_sample is True

    def test_n_races_option(self, monkeypatch):
        """--n-races が反映されること"""
        monkeypatch.setattr(sys, "argv", ["train_model.py", "--use-sample", "--n-races", "500"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.n_races == 500

    def test_auto_promote_flag(self, monkeypatch):
        """--auto-promote フラグが True になること"""
        monkeypatch.setattr(sys, "argv", ["train_model.py", "--use-sample", "--auto-promote"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.auto_promote is True

    def test_notes_option(self, monkeypatch):
        """--notes が文字列として取得されること"""
        monkeypatch.setattr(sys, "argv", ["train_model.py", "--notes", "本番投入用"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.notes == "本番投入用"

    def test_model_name_option(self, monkeypatch):
        """--model-name が反映されること"""
        monkeypatch.setattr(sys, "argv", ["train_model.py", "--model-name", "custom_model"])
        from scripts.train_model import parse_args
        args = parse_args()
        assert args.model_name == "custom_model"


# ============================================================
# main() フロー
# ============================================================

FAKE_METRICS = {
    "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
    "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
    "n_samples": 1200, "feature_columns": ["x"] * 12,
}


class TestMainUseSample:
    def test_runs_without_error(self, tmp_path, monkeypatch):
        """--use-sample で例外なく完了すること"""
        import app.model.versioning as ver_mod
        import app.model.train as train_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--use-sample", "--n-races", "200", "--n-splits", "2"
        ])

        from scripts.train_model import main
        main()

    def test_registers_version(self, tmp_path, monkeypatch):
        """main() 後にレジストリにバージョンが登録されること"""
        import app.model.versioning as ver_mod
        import app.model.train as train_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--use-sample", "--n-races", "200", "--n-splits", "2"
        ])

        from scripts.train_model import main
        from app.model.versioning import ModelRegistry
        main()
        reg = ModelRegistry()
        assert len(reg.list_versions()) >= 1

    def test_auto_promote_sets_production(self, tmp_path, monkeypatch):
        """--auto-promote で学習後に本番モデルが設定されること"""
        import app.model.versioning as ver_mod
        import app.model.train as train_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--use-sample", "--n-races", "200",
            "--n-splits", "2", "--auto-promote",
        ])

        from scripts.train_model import main
        from app.model.versioning import ModelRegistry
        main()
        reg = ModelRegistry()
        assert reg.get_production_version() is not None

    def test_metrics_printed(self, tmp_path, monkeypatch, capsys):
        """学習メトリクスが stdout に出力されること"""
        import app.model.versioning as ver_mod
        import app.model.train as train_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--use-sample", "--n-races", "200", "--n-splits", "2"
        ])

        from scripts.train_model import main
        main()
        out = capsys.readouterr().out
        assert "cv_logloss_mean" in out

    def test_notes_saved_to_registry(self, tmp_path, monkeypatch):
        """--notes が登録バージョンのメタデータに保存されること"""
        import app.model.versioning as ver_mod
        import app.model.train as train_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--use-sample", "--n-races", "200",
            "--n-splits", "2", "--notes", "CI自動学習",
        ])

        from scripts.train_model import main
        from app.model.versioning import ModelRegistry
        main()
        reg = ModelRegistry()
        versions = reg.list_versions()
        assert any("CI自動学習" in v.get("notes", "") for v in versions)


class TestMainDataPath:
    def test_missing_data_path_raises(self, tmp_path, monkeypatch):
        """存在しない --data-path で FileNotFoundError (または SystemExit) が出ること"""
        monkeypatch.setattr(sys, "argv", [
            "train_model.py", "--data-path", str(tmp_path / "nope.csv")
        ])
        from scripts.train_model import main
        with pytest.raises((FileNotFoundError, SystemExit)):
            main()
