"""
app/cli.py のテスト

Click の CliRunner を使って各サブコマンドを検証する。
subprocess 呼び出し系はモックして実行を回避する。
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_versioning import _PicklableModel


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli_registry(tmp_path, monkeypatch):
    """テスト用 ModelRegistry（バージョン2件登録済み）を返す"""
    import app.model.versioning as ver_mod
    monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

    from app.model.versioning import ModelRegistry
    registry = ModelRegistry()
    metrics = {
        "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
        "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
        "n_samples": 1000, "feature_columns": ["x"] * 12,
    }
    registry.register(_PicklableModel(), metrics)
    registry.register(_PicklableModel(), metrics)
    return registry, tmp_path


# ============================================================
# model グループ
# ============================================================

class TestModelList:
    def test_exits_zero(self, runner, cli_registry):
        """model list がエラーなく完了すること"""
        from app.cli import cli
        result = runner.invoke(cli, ["model", "list"])
        assert result.exit_code == 0


class TestModelPromote:
    def test_latest_promotes(self, runner, cli_registry):
        """--latest --yes で最新を本番に昇格すること"""
        registry, _ = cli_registry
        from app.cli import cli
        result = runner.invoke(cli, ["model", "promote", "--latest", "--yes"])
        assert result.exit_code == 0
        # 再読み込みして本番バージョンが設定されていること
        from app.model.versioning import ModelRegistry
        reg2 = ModelRegistry()
        assert reg2.get_production_version() is not None

    def test_specific_version_promotes(self, runner, cli_registry):
        """--version <name> --yes で特定バージョンを昇格できること"""
        registry, _ = cli_registry
        target = registry.list_versions()[0]["version"]
        from app.cli import cli
        result = runner.invoke(cli, ["model", "promote", "--version", target, "--yes"])
        assert result.exit_code == 0

    def test_no_arg_exits_nonzero(self, runner, cli_registry):
        """引数なしで --version/--latest が無いとエラー終了すること"""
        from app.cli import cli
        result = runner.invoke(cli, ["model", "promote"])
        assert result.exit_code != 0

    def test_latest_without_versions_exits(self, runner, tmp_path, monkeypatch):
        """--latest でバージョンなしのときエラー終了すること"""
        import app.model.versioning as ver_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "empty.json")

        from app.cli import cli
        result = runner.invoke(cli, ["model", "promote", "--latest"])
        assert result.exit_code != 0


class TestModelCleanup:
    def test_cleanup_no_targets(self, runner, tmp_path, monkeypatch):
        """削除対象がないとき正常終了すること"""
        import app.model.versioning as ver_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "empty.json")

        from app.cli import cli
        result = runner.invoke(cli, ["model", "cleanup", "--keep", "10", "--yes"])
        assert result.exit_code == 0
        assert "削除対象なし" in result.output or "登録数" in result.output

    def test_cleanup_removes_extras(self, runner, tmp_path, monkeypatch):
        """--keep 未満まで削除すること"""
        import app.model.versioning as ver_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "reg.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.0,
            "cv_accuracy_mean": 0.2, "cv_accuracy_std": 0.0,
            "n_samples": 10, "feature_columns": ["x"] * 12,
        }
        for _ in range(5):
            registry.register(_PicklableModel(), metrics)

        from app.cli import cli
        result = runner.invoke(cli, ["model", "cleanup", "--keep", "2", "--yes"])
        assert result.exit_code == 0

        reg2 = ModelRegistry()
        assert len(reg2.list_versions()) <= 2


# ============================================================
# api グループ
# ============================================================

class TestApiKeygen:
    def test_generates_one_key(self, runner):
        """api keygen でキーが1件出力されること"""
        from app.cli import cli
        result = runner.invoke(cli, ["api", "keygen"])
        assert result.exit_code == 0
        # デフォルトプレフィックス "br" で始まるキーが含まれる
        assert "br" in result.output

    def test_count_option(self, runner):
        """--count 3 で3件生成されること"""
        from app.cli import cli
        result = runner.invoke(cli, ["api", "keygen", "--count", "3"])
        assert result.exit_code == 0
        # 3行以上出力される（ヘッダー含む）
        assert result.output.count("br") >= 3

    def test_custom_prefix(self, runner):
        """--prefix を指定したときそのプレフィックスで生成されること"""
        from app.cli import cli
        result = runner.invoke(cli, ["api", "keygen", "--prefix", "test"])
        assert result.exit_code == 0
        assert "test" in result.output


class TestApiHealth:
    def test_connection_failure_exits_nonzero(self, runner):
        """到達不能な URL ではエラー終了すること"""
        import requests
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("down")):
            from app.cli import cli
            result = runner.invoke(cli, ["api", "health", "--url", "http://localhost:9"])
        assert result.exit_code != 0

    def test_success_shows_status(self, runner):
        """正常レスポンス時にステータスが表示されること"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "ok",
            "uptime_sec": 123,
            "checks": {"db": {"status": "ok"}},
        }
        with patch("requests.get", return_value=mock_resp):
            from app.cli import cli
            result = runner.invoke(cli, ["api", "health"])
        assert result.exit_code == 0
        assert "ok" in result.output


# ============================================================
# data グループ
# ============================================================

class TestDataValidate:
    def test_missing_file_exits_nonzero(self, runner, tmp_path):
        """存在しないファイル指定でエラー終了すること"""
        from app.cli import cli
        result = runner.invoke(cli, ["data", "validate", "--path", str(tmp_path / "nope.csv")])
        assert result.exit_code != 0
        assert "見つかりません" in result.output


# ============================================================
# result グループ
# ============================================================

class TestResultRecord:
    def test_creates_json_file(self, runner, tmp_path, monkeypatch):
        """レース結果 JSON が生成されること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["result", "record", "race_001", "3"])
        assert result.exit_code == 0
        path = tmp_path / "data/race_results/race_001.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["race_id"] == "race_001"
        assert data["true_winner"] == 3

    def test_duplicate_exits_nonzero(self, runner, tmp_path, monkeypatch):
        """同じ race_id で2回記録するとエラーになること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        runner.invoke(cli, ["result", "record", "race_dup", "1"])
        result = runner.invoke(cli, ["result", "record", "race_dup", "2"])
        assert result.exit_code != 0

    def test_invalid_winner_rejected(self, runner, tmp_path, monkeypatch):
        """7号艇（範囲外）は Click バリデーションで拒否されること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["result", "record", "race_x", "7"])
        assert result.exit_code != 0

    def test_with_second_third(self, runner, tmp_path, monkeypatch):
        """--second / --third オプションが保存されること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(
            cli,
            ["result", "record", "race_ext", "3", "--second", "1", "--third", "5"],
        )
        assert result.exit_code == 0
        data = json.loads((tmp_path / "data/race_results/race_ext.json").read_text())
        assert data["second_place"] == 1
        assert data["third_place"] == 5


class TestResultSummary:
    def test_no_results_shows_message(self, runner, tmp_path, monkeypatch):
        """レコードなしで「記録なし」を出力すること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["result", "summary"])
        assert result.exit_code == 0
        assert "記録なし" in result.output

    def test_with_records_shows_hit_rate(self, runner, tmp_path, monkeypatch):
        """記録があるとき的中率が表示されること"""
        monkeypatch.chdir(tmp_path)
        result_dir = tmp_path / "data/race_results"
        result_dir.mkdir(parents=True)
        for i in range(5):
            rec = {
                "race_id": f"r{i}",
                "is_correct": i % 2 == 0,
                "prediction_rank": (i % 6) + 1,
            }
            (result_dir / f"r{i}.json").write_text(json.dumps(rec))

        from app.cli import cli
        result = runner.invoke(cli, ["result", "summary"])
        assert result.exit_code == 0
        assert "的中率" in result.output


# ============================================================
# shadow グループ
# ============================================================

class TestShadowStats:
    def test_no_log_shows_message(self, runner, tmp_path, monkeypatch):
        """ログなしで「見つかりません」を表示すること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "stats", "--name", "nonexistent"])
        assert result.exit_code == 0
        assert "見つかりません" in result.output

    def test_computes_match_rate(self, runner, tmp_path, monkeypatch):
        """ログから一致率が計算されること"""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "data/shadow_logs"
        log_dir.mkdir(parents=True)
        entries = [
            {"top1_match": True,  "kl_divergence": 0.01},
            {"top1_match": False, "kl_divergence": 0.05},
        ]
        (log_dir / "shadow.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )

        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "stats", "--name", "shadow"])
        assert result.exit_code == 0
        assert "1位一致率" in result.output
        assert "50.0%" in result.output


# ============================================================
# エントリー / バージョン
# ============================================================

# ============================================================
# scoring グループ
# ============================================================

def _write_pred(path: Path, race_id: str, win_proba: list,
                jyo_code: str = "01", race_date: str = "20260420") -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {
        "race_id":           race_id,
        "jyo_code":          jyo_code,
        "race_date":         race_date,
        "win_probabilities": win_proba,
    }
    (path / f"{race_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )


def _write_res(path: Path, race_id: str, true_winner: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {"race_id": race_id, "true_winner": true_winner}
    (path / f"{race_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )


class TestScoringCli:
    def test_overview_no_data(self, runner, tmp_path, monkeypatch):
        """予測・結果データなしのとき 'データなし' が表示されること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview"])
        assert result.exit_code == 0
        assert "データなし" in result.output

    def test_overview_with_data(self, runner, tmp_path, monkeypatch):
        """予測と結果が揃っているとき的中率が表示されること"""
        monkeypatch.chdir(tmp_path)
        pred_dir   = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        _write_pred(pred_dir, "r1", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_pred(pred_dir, "r2", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_res(result_dir, "r1", true_winner=1)   # 的中
        _write_res(result_dir, "r2", true_winner=3)   # 外れ

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview"])
        assert result.exit_code == 0
        assert "突き合わせ数" in result.output
        assert "50.0%" in result.output

    def test_overview_date_filter(self, runner, tmp_path, monkeypatch):
        """--date フィルターが動作すること"""
        monkeypatch.chdir(tmp_path)
        pred_dir   = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        _write_pred(pred_dir, "r1", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1], race_date="20260420")
        _write_pred(pred_dir, "r2", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1], race_date="20260421")
        _write_res(result_dir, "r1", true_winner=1)
        _write_res(result_dir, "r2", true_winner=1)

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview", "--date", "20260420"])
        assert result.exit_code == 0
        assert "20260420" in result.output

    def test_overview_venue_filter(self, runner, tmp_path, monkeypatch):
        """--venue フィルターが動作すること"""
        monkeypatch.chdir(tmp_path)
        pred_dir   = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        _write_pred(pred_dir, "r1", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1], jyo_code="06")
        _write_res(result_dir, "r1", true_winner=1)

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview", "--venue", "06"])
        assert result.exit_code == 0
        assert "06" in result.output

    def test_race_both_present(self, runner, tmp_path, monkeypatch):
        """予測と結果が両方あるとき照合結果が表示されること"""
        monkeypatch.chdir(tmp_path)
        pred_dir   = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        _write_pred(pred_dir, "r_match", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_res(result_dir, "r_match", true_winner=1)

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_match"])
        assert result.exit_code == 0
        assert "的中" in result.output
        assert "1号艇" in result.output

    def test_race_miss(self, runner, tmp_path, monkeypatch):
        """予測1位と実際の1着が異なるとき '外れ' が表示されること"""
        monkeypatch.chdir(tmp_path)
        pred_dir   = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        _write_pred(pred_dir, "r_miss", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_res(result_dir, "r_miss", true_winner=3)

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_miss"])
        assert result.exit_code == 0
        assert "外れ" in result.output

    def test_race_not_found(self, runner, tmp_path, monkeypatch):
        """存在しない race_id のとき exit_code=1 になること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "no_such_race"])
        assert result.exit_code == 1

    def test_race_prediction_only(self, runner, tmp_path, monkeypatch):
        """予測のみ（結果未記録）のとき '結果未記録' が表示されること"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        _write_pred(pred_dir, "r_pred_only", [1/6] * 6)

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_pred_only"])
        assert result.exit_code == 0
        assert "結果未記録" in result.output


# ============================================================
# エントリー / バージョン
# ============================================================

class TestCliEntry:
    def test_version_flag(self, runner):
        """--version オプションが動作すること"""
        from app.cli import cli
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "boat-race-ai" in result.output

    def test_help_flag(self, runner):
        """--help オプションが動作すること"""
        from app.cli import cli
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "scoring" in result.output
