"""
A/B テストモジュールのユニットテスト
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# フィクスチャ
# ============================================================

def _make_mock_model(seed: int = 0):
    """テスト用モックモデル（predict_proba を持つ）"""
    rng = np.random.default_rng(seed)
    model = MagicMock()
    model.predict_proba.side_effect = lambda X: rng.dirichlet(
        np.ones(6), size=6
    )
    return model


@pytest.fixture
def router(tmp_path, monkeypatch):
    """テスト用 ABTestRouter（ファイル出力を tmp_path に隔離）"""
    import app.model.ab_test as ab_module
    monkeypatch.setattr(ab_module, "AB_LOG_DIR", tmp_path / "ab_logs")

    from app.model.ab_test import ABTestRouter
    r = ABTestRouter(name="test")
    r.add_variant("control",    _make_mock_model(0), traffic_weight=0.7)
    r.add_variant("challenger", _make_mock_model(1), traffic_weight=0.3)
    return r


@pytest.fixture
def sample_X():
    """ダミー特徴量行列 shape=(6, 12)"""
    return np.random.default_rng(42).random((6, 12))


# ============================================================
# add_variant / _select_variant
# ============================================================

class TestVariantSelection:
    def test_add_variant_count(self, router):
        """add_variant() でバリアントが正しく追加される"""
        assert len(router._variants) == 2

    def test_select_variant_deterministic(self, router):
        """同じ race_id は常に同じバリアントに割り当てられる"""
        v1 = router._select_variant("race_001")
        v2 = router._select_variant("race_001")
        assert v1.name == v2.name

    def test_select_variant_different_ids(self, router):
        """異なる race_id は分散して割り当てられる（偏りのない検証）"""
        names = {router._select_variant(f"race_{i:04d}").name for i in range(200)}
        # 200リクエストでは両バリアントに振られるはず
        assert len(names) == 2

    def test_weight_distribution(self, router):
        """トラフィック配分が重み設定（0.7/0.3）に概ね従う"""
        counts = {"control": 0, "challenger": 0}
        for i in range(2000):
            v = router._select_variant(f"race_{i:05d}")
            counts[v.name] += 1
        ratio = counts["control"] / 2000
        # 0.7 ±0.05 の範囲に収まることを確認
        assert 0.65 <= ratio <= 0.75


# ============================================================
# predict
# ============================================================

class TestPredict:
    def test_predict_returns_variant_and_proba(self, router, sample_X):
        """predict() がバリアント名と確率行列を返す"""
        variant_name, proba = router.predict(sample_X, race_id="race_001")
        assert isinstance(variant_name, str)
        assert proba.shape == (6, 6)

    def test_predict_increments_n_requests(self, router, sample_X):
        """predict() を呼ぶとバリアントのリクエスト数が増える"""
        before = sum(v.n_requests for v in router._variants)
        router.predict(sample_X, race_id="race_001")
        after = sum(v.n_requests for v in router._variants)
        assert after == before + 1

    def test_predict_records_race_log(self, router, sample_X):
        """predict() の結果が _race_log に記録される"""
        router.predict(sample_X, race_id="race_xyz")
        assert "race_xyz" in router._race_log
        log = router._race_log["race_xyz"]
        assert "variant" in log
        assert "predicted_1st" in log
        assert "proba" in log

    def test_predict_no_variants_raises(self):
        """バリアント未登録で predict() を呼ぶと RuntimeError"""
        from app.model.ab_test import ABTestRouter
        empty_router = ABTestRouter(name="empty")
        with pytest.raises(RuntimeError):
            empty_router.predict(np.zeros((6, 12)), race_id="x")


# ============================================================
# record_result
# ============================================================

class TestRecordResult:
    def test_record_result_updates_correct(self, router, sample_X, tmp_path):
        """正解を記録すると n_correct が増える"""
        race_id = "race_001"
        variant_name, proba = router.predict(sample_X, race_id=race_id)

        # 予測1位の艇番を正解として渡す → n_correct が 1 増えるはず
        predicted_boat = int(np.argmax(proba[:, 0])) + 1
        variant = next(v for v in router._variants if v.name == variant_name)
        before = variant.n_correct

        router.record_result(race_id=race_id, true_winner=predicted_boat)
        assert variant.n_correct == before + 1

    def test_record_result_updates_log_loss(self, router, sample_X):
        """record_result() で log_loss_sum が更新される"""
        race_id = "race_002"
        variant_name, _ = router.predict(sample_X, race_id=race_id)
        variant = next(v for v in router._variants if v.name == variant_name)
        before = variant.log_loss_sum

        router.record_result(race_id=race_id, true_winner=1)
        assert variant.log_loss_sum > before

    def test_record_result_unknown_race_warns(self, router, caplog):
        """predict() を呼んでいないレースで record_result() すると警告"""
        import logging
        with caplog.at_level(logging.WARNING):
            router.record_result(race_id="never_predicted", true_winner=1)
        assert "predict()" in caplog.text or "呼ばれていない" in caplog.text

    def test_record_result_saves_jsonl(self, router, sample_X, tmp_path):
        """record_result() が JSONL ファイルを書き出す"""
        import app.model.ab_test as ab_module
        log_dir = tmp_path / "ab_logs"
        router.predict(sample_X, race_id="race_save")
        router.record_result(race_id="race_save", true_winner=2)
        jsonl_path = log_dir / "test.jsonl"
        assert jsonl_path.exists()
        import json
        lines = jsonl_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["race_id"] == "race_save"


# ============================================================
# get_report / print_report
# ============================================================

class TestReport:
    def _run_n_races(self, router, sample_X, n: int):
        """n レース分の predict + record_result を実行"""
        rng = np.random.default_rng(99)
        for i in range(n):
            race_id = f"race_{i:04d}"
            router.predict(sample_X, race_id=race_id)
            router.record_result(race_id=race_id, true_winner=rng.integers(1, 7))

    def test_report_structure(self, router, sample_X):
        """get_report() が必要フィールドを持つ ABTestReport を返す"""
        self._run_n_races(router, sample_X, 5)
        report = router.get_report()
        assert hasattr(report, "variants")
        assert hasattr(report, "winner")
        assert hasattr(report, "is_significant")
        assert hasattr(report, "p_value")
        assert hasattr(report, "message")

    def test_report_variant_stats(self, router, sample_X):
        """レポートの variants リストに各バリアントの統計が含まれる"""
        self._run_n_races(router, sample_X, 20)
        report = router.get_report()
        assert len(report.variants) == 2
        for v in report.variants:
            assert "name" in v
            assert "n_requests" in v
            assert "hit_rate" in v
            assert "avg_latency_ms" in v
            assert "avg_log_loss" in v

    def test_report_insufficient_variants(self):
        """バリアントが1つ以下では適切なメッセージが返る"""
        from app.model.ab_test import ABTestRouter
        r = ABTestRouter(name="single")
        r.add_variant("only", _make_mock_model(), traffic_weight=1.0)
        report = r.get_report()
        assert report.is_significant is False
        assert report.p_value == 1.0

    def test_print_report_no_error(self, router, sample_X, capsys):
        """print_report() がエラーなく実行できる"""
        self._run_n_races(router, sample_X, 5)
        router.print_report()
        captured = capsys.readouterr()
        assert "A/B テスト結果" in captured.out

    def test_significance_with_enough_data(self, tmp_path, monkeypatch):
        """十分なデータで有意差がある場合に winner が設定される（モック）"""
        import app.model.ab_test as ab_module
        monkeypatch.setattr(ab_module, "AB_LOG_DIR", tmp_path / "ab_logs")

        from app.model.ab_test import ABTestRouter
        router = ABTestRouter(name="sig_test")
        router.add_variant("control",    _make_mock_model(0), traffic_weight=0.5)
        router.add_variant("challenger", _make_mock_model(1), traffic_weight=0.5)

        # n_requests と n_correct を直接操作して有意差を作る
        router._variants[0].n_requests = 200
        router._variants[0].n_correct  = 80   # 40%
        router._variants[1].n_requests = 200
        router._variants[1].n_correct  = 40   # 20%

        report = router.get_report()
        assert report.is_significant is True
        assert report.winner == "control"
        assert report.p_value < 0.05
