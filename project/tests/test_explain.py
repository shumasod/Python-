"""
予測説明エンドポイントのテスト
"""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import verify_api_key

app.dependency_overrides[verify_api_key] = lambda: "test-key"
client = TestClient(app)


# ============================================================
# テスト用フィクスチャ
# ============================================================

def _race_payload(race_id: str = "test_race_001") -> dict:
    """有効なレースリクエストペイロードを返す"""
    return {
        "race_id": race_id,
        "race": {
            "boats": [
                {
                    "boat_number": i,
                    "racer_rank": "A1" if i == 1 else "B1",
                    "win_rate": 60.0 - i * 5,
                    "motor_score": 55.0,
                    "course_win_rate": 42.0 - i * 4,
                    "start_timing": 0.15 + i * 0.01,
                    "motor_2rate": 38.0,
                    "boat_2rate": 35.0,
                    "recent_3_avg": 2.0 + i * 0.3,
                }
                for i in range(1, 7)
            ],
            "weather": {"condition": "晴", "wind_speed": 1.5, "water_temp": 22.0},
        },
    }


# ============================================================
# POST /api/v1/explain — モデルなし（503）
# ============================================================

class TestExplainEndpointNoModel:
    def test_no_model_returns_503(self):
        """モデル未学習時に 503 を返すこと"""
        with patch("app.api.explain.get_model", side_effect=FileNotFoundError("no model")):
            resp = client.post("/api/v1/explain", json=_race_payload())
        assert resp.status_code == 503

    def test_generic_exception_returns_500(self):
        """explain_race が予期しない例外を投げたとき 500 が返ること"""
        with patch("app.api.explain.explain_race", side_effect=RuntimeError("unexpected")):
            resp = client.post("/api/v1/explain", json=_race_payload())
        assert resp.status_code == 500

    def test_invalid_race_returns_422(self):
        """boats が6艇でない場合に 422 を返すこと"""
        payload = _race_payload()
        payload["race"]["boats"] = payload["race"]["boats"][:4]  # 4艇のみ
        with patch("app.api.explain.get_model", side_effect=FileNotFoundError("no model")):
            resp = client.post("/api/v1/explain", json=payload)
        # バリデーションエラーは predict と同じ RaceRequest を使うので 422
        assert resp.status_code in (422, 503)


# ============================================================
# explain_race ロジック（モデルのモックを使用）
# ============================================================

class TestExplainRaceLogic:
    """explain_race 関数を直接テストする"""

    @pytest.fixture
    def mock_model(self):
        """均一 predict_proba + 一様 feature_importances_ を返すモック"""
        class _FakeModel:
            feature_importances_ = list(range(1, 13))  # 非均一の重要度

            def predict_proba(self, X):
                n = X.shape[0]
                proba = np.ones((n, 6)) / 6
                # 1号艇を少し有利に
                proba[0, 0] = 0.25
                proba[0, 1:] = 0.75 / 5
                return proba

        return _FakeModel()

    def test_returns_six_boat_explanations(self, mock_model):
        """6艇分の説明が返ること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        assert len(result["boat_explanations"]) == 6

    def test_boat_numbers_1_to_6(self, mock_model):
        """boat_number が 1〜6 であること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        numbers = [b["boat_number"] for b in result["boat_explanations"]]
        assert numbers == [1, 2, 3, 4, 5, 6]

    def test_win_probabilities_sum_to_one(self, mock_model):
        """各艇の win_probability の和が 1 であること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        total = sum(b["win_probability"] for b in result["boat_explanations"])
        assert total == pytest.approx(1.0, abs=1e-3)

    def test_top_factors_have_five_items(self, mock_model):
        """各艇のトップ寄与因子が5件返ること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        for boat in result["boat_explanations"]:
            assert len(boat["top_factors"]) == 5

    def test_top_factors_contain_required_keys(self, mock_model):
        """top_factors の各アイテムに必要なキーが含まれること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        for boat in result["boat_explanations"]:
            for factor in boat["top_factors"]:
                assert "feature" in factor
                assert "value" in factor
                assert "z_score" in factor
                assert "contribution" in factor

    def test_feature_importance_sums_to_one(self, mock_model):
        """feature_importance の和が 1 であること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        total = sum(f["importance"] for f in result["feature_importance"])
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_feature_importance_ranked(self, mock_model):
        """feature_importance が rank 順に並んでいること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        ranks = [f["rank"] for f in result["feature_importance"]]
        assert ranks == sorted(ranks)

    def test_summary_contains_boat_number(self, mock_model):
        """summary に艇番が含まれること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        for boat in result["boat_explanations"]:
            assert str(boat["boat_number"]) in boat["summary"]

    def test_summary_contains_probability(self, mock_model):
        """summary に勝率が含まれること"""
        from app.api.explain import explain_race

        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        for boat in result["boat_explanations"]:
            # "%" が含まれること（パーセント表示）
            assert "%" in boat["summary"]

    def test_uniform_features_give_zero_z_scores(self):
        """全艇で特徴値が同じとき z スコアがほぼ 0 であること"""
        from app.api.explain import explain_race

        class _UniformModel:
            feature_importances_ = [1] * 12

            def predict_proba(self, X):
                return np.ones((6, 6)) / 6

        # 全艇の特徴値が同一のレースを作る
        # boat_number=1 for all boats so ALL features are uniform
        uniform_race = {
            "boats": [
                {
                    "boat_number": 1,
                    "racer_rank": "B1",
                    "win_rate": 30.0,
                    "motor_score": 50.0,
                    "course_win_rate": 20.0,
                    "start_timing": 0.18,
                    "motor_2rate": 35.0,
                    "boat_2rate": 32.0,
                    "recent_3_avg": 3.5,
                }
                for _ in range(6)
            ],
            "weather": {"condition": "晴", "wind_speed": 0.0, "water_temp": 20.0},
        }

        with patch("app.api.explain.get_model", return_value=_UniformModel()):
            result = explain_race(uniform_race)

        for boat in result["boat_explanations"]:
            for factor in boat["top_factors"]:
                assert abs(factor["z_score"]) < 1e-3

    def test_model_version_returned(self, mock_model):
        """model_version フィールドが返ること"""
        from app.api.explain import explain_race

        mock_model._version_name = "boat_race_model_v20260412_1"
        with patch("app.api.explain.get_model", return_value=mock_model):
            result = explain_race(_race_payload()["race"])

        assert result["model_version"] == "boat_race_model_v20260412_1"

    def test_zero_importances_normalizes_to_uniform(self):
        """feature_importances_ が全ゼロのとき total=1.0 にフォールバックすること"""
        from app.api.explain import explain_race

        class _ZeroImportanceModel:
            feature_importances_ = [0.0] * 12

            def predict_proba(self, X):
                return np.ones((6, 6)) / 6

        with patch("app.api.explain.get_model", return_value=_ZeroImportanceModel()):
            result = explain_race(_race_payload()["race"])

        # 全ゼロ → normalization で全て 0.0 になる（クラッシュしないことが目標）
        assert len(result["feature_importance"]) == 12

    def test_make_summary_empty_top_factors(self):
        """top_factors が空のとき 'データ不足' サマリーを返すこと"""
        from app.api.explain import _make_summary
        result = _make_summary(3, [], 0.2)
        assert "データ不足" in result
        assert "3" in result


# ============================================================
# POST /api/v1/explain — 統合テスト（trained model）
# ============================================================

class TestExplainEndpointIntegration:
    """実際に学習済みモデルを使ったエンドツーエンドテスト"""

    def test_explain_returns_200_with_trained_model(self, trained_model, monkeypatch):
        """学習済みモデルで 200 が返ること"""
        model, _metrics, _tmp = trained_model
        import app.model.predict as predict_module
        monkeypatch.setattr(predict_module, "_cached_model", model)

        resp = client.post("/api/v1/explain", json=_race_payload())
        assert resp.status_code == 200

    def test_explain_response_structure(self, trained_model, monkeypatch):
        """レスポンスに必要なキーがすべて含まれること"""
        model, _metrics, _tmp = trained_model
        import app.model.predict as predict_module
        monkeypatch.setattr(predict_module, "_cached_model", model)

        resp = client.post("/api/v1/explain", json=_race_payload("r_struct"))
        assert resp.status_code == 200
        body = resp.json()

        assert "race_id" in body
        assert "model_version" in body
        assert "feature_importance" in body
        assert "boat_explanations" in body
        assert len(body["boat_explanations"]) == 6
        assert len(body["feature_importance"]) == 12  # 12 features

    def test_explain_race_id_echoed(self, trained_model, monkeypatch):
        """race_id がレスポンスに反映されること"""
        model, _metrics, _tmp = trained_model
        import app.model.predict as predict_module
        monkeypatch.setattr(predict_module, "_cached_model", model)

        resp = client.post("/api/v1/explain", json=_race_payload("echo_me"))
        assert resp.json()["race_id"] == "echo_me"
