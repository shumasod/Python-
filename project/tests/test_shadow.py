"""
シャドウモードモジュールのユニットテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def runner(tmp_path, monkeypatch):
    """テスト用 ShadowRunner（ログを tmp_path に隔離）"""
    import app.model.shadow as shadow_module
    monkeypatch.setattr(shadow_module, "SHADOW_LOG_DIR", tmp_path / "shadow_logs")

    from app.model.shadow import ShadowRunner

    model = MagicMock()
    model.predict_proba.return_value = np.full((6, 6), 1 / 6)
    return ShadowRunner(shadow_model=model, sample_rate=1.0, name="test")


@pytest.fixture
def prod_proba():
    """ダミー本番モデル確率行列 shape=(6, 6)"""
    rng = np.random.default_rng(0)
    p = rng.dirichlet(np.ones(6), size=6)
    return p


class TestShadowSampling:
    def test_sample_rate_1_always_runs(self, runner, prod_proba):
        """sample_rate=1.0 ではすべてのリクエストが実行される"""
        X = np.zeros((6, 12))
        for i in range(10):
            result = runner.run_shadow(X, f"race_{i:03d}", prod_proba)
            assert result is not None

    def test_sample_rate_0_never_runs(self, tmp_path, monkeypatch, prod_proba):
        """sample_rate=0.0 ではリクエストが一切実行されない"""
        import app.model.shadow as shadow_module
        monkeypatch.setattr(shadow_module, "SHADOW_LOG_DIR", tmp_path / "shadow_logs")
        from app.model.shadow import ShadowRunner

        model = MagicMock()
        r = ShadowRunner(shadow_model=model, sample_rate=0.0, name="zero")
        X = np.zeros((6, 12))
        for i in range(50):
            result = r.run_shadow(X, f"race_{i:04d}", prod_proba)
            assert result is None
        model.predict_proba.assert_not_called()

    def test_deterministic_sampling(self, runner, prod_proba):
        """同じ race_id は常に同じサンプリング結果になる"""
        X = np.zeros((6, 12))
        r1 = runner._should_run("race_deterministic")
        r2 = runner._should_run("race_deterministic")
        assert r1 == r2


class TestShadowRecord:
    def test_record_fields(self, runner, prod_proba):
        """ShadowRecord に必要なフィールドが含まれる"""
        from app.model.shadow import ShadowRecord

        X = np.zeros((6, 12))
        record = runner.run_shadow(X, "race_001", prod_proba)
        assert isinstance(record, ShadowRecord)
        assert hasattr(record, "race_id")
        assert hasattr(record, "prod_top1")
        assert hasattr(record, "shadow_top1")
        assert hasattr(record, "kl_divergence")
        assert hasattr(record, "top1_match")
        assert hasattr(record, "shadow_latency_ms")

    def test_kl_divergence_same_dist(self):
        """同一分布の KL ダイバージェンスは 0 に近い"""
        from app.model.shadow import ShadowRunner

        p = np.array([0.4, 0.2, 0.15, 0.1, 0.1, 0.05])
        kl = ShadowRunner._kl_divergence(p, p.copy())
        assert kl < 1e-6

    def test_kl_divergence_different_dist(self):
        """異なる分布の KL ダイバージェンスは正値"""
        from app.model.shadow import ShadowRunner

        p = np.array([0.5, 0.2, 0.1, 0.1, 0.05, 0.05])
        q = np.array([0.1, 0.1, 0.1, 0.2, 0.2, 0.3])
        kl = ShadowRunner._kl_divergence(p, q)
        assert kl > 0

    def test_top1_match_when_same_model(self, tmp_path, monkeypatch, prod_proba):
        """同じ確率を返すモデルでは top1_match=True"""
        import app.model.shadow as shadow_module
        monkeypatch.setattr(shadow_module, "SHADOW_LOG_DIR", tmp_path / "shadow_logs")
        from app.model.shadow import ShadowRunner

        # 本番モデルと全く同じ確率を返すシャドウ
        model = MagicMock()
        model.predict_proba.return_value = prod_proba.copy()

        runner = ShadowRunner(shadow_model=model, sample_rate=1.0, name="same")
        X = np.zeros((6, 12))
        record = runner.run_shadow(X, "race_same", prod_proba)
        assert record.top1_match is True


class TestShadowStats:
    def _run_n(self, runner, n: int, prod_proba: np.ndarray):
        X = np.zeros((6, 12))
        for i in range(n):
            runner.run_shadow(X, f"race_{i:04d}", prod_proba)

    def test_n_sampled_increments(self, runner, prod_proba):
        """run_shadow() を呼ぶたびに n_sampled が増える"""
        self._run_n(runner, 5, prod_proba)
        assert runner.get_stats()["n_sampled"] == 5

    def test_match_rate_range(self, runner, prod_proba):
        """top1_match_rate が 0〜1 の範囲に収まる"""
        self._run_n(runner, 20, prod_proba)
        stats = runner.get_stats()
        assert 0.0 <= stats["top1_match_rate"] <= 1.0

    def test_stats_empty(self, tmp_path, monkeypatch):
        """サンプルゼロのとき None を返す"""
        import app.model.shadow as shadow_module
        monkeypatch.setattr(shadow_module, "SHADOW_LOG_DIR", tmp_path / "shadow_logs")
        from app.model.shadow import ShadowRunner

        r = ShadowRunner(MagicMock(), sample_rate=0.0, name="empty")
        stats = r.get_stats()
        assert stats["top1_match_rate"] is None
        assert stats["avg_kl"] is None

    def test_print_stats_no_error(self, runner, prod_proba, capsys):
        """print_stats() がエラーなく実行できる"""
        self._run_n(runner, 3, prod_proba)
        runner.print_stats()
        captured = capsys.readouterr()
        assert "シャドウモード統計" in captured.out


class TestShadowPersistence:
    def test_saves_jsonl(self, runner, prod_proba, tmp_path):
        """run_shadow() が JSONL ファイルに記録を保存する"""
        import app.model.shadow as shadow_module

        X = np.zeros((6, 12))
        runner.run_shadow(X, "race_save", prod_proba)

        log_path = tmp_path / "shadow_logs" / "test.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip())
        assert entry["race_id"] == "race_save"
        assert "kl_divergence" in entry
        assert "top1_match" in entry

    def test_multiple_records_appended(self, runner, prod_proba, tmp_path):
        """複数レコードがファイルに追記される"""
        X = np.zeros((6, 12))
        for i in range(3):
            runner.run_shadow(X, f"race_{i}", prod_proba)

        log_path = tmp_path / "shadow_logs" / "test.jsonl"
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
