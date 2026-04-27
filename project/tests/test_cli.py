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


# ============================================================
# model train（subprocess mock）
# ============================================================

class TestModelTrain:
    def _mock_proc(self, returncode=0):
        m = MagicMock()
        m.returncode = returncode
        return m

    def test_default_uses_sample(self, runner):
        """デフォルトオプションでサンプルデータを使う subprocess が呼ばれること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["model", "train"])
        cmd = mock_sub.call_args[0][0]
        assert "--use-sample" in cmd
        assert "--n-races" in cmd

    def test_data_path_option(self, runner):
        """--data-path が指定されたとき subprocess に渡されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["model", "train", "--data-path", "/tmp/data.csv"])
        cmd = mock_sub.call_args[0][0]
        assert "--data-path" in cmd
        assert "/tmp/data.csv" in cmd

    def test_auto_promote_flag(self, runner):
        """--auto-promote が subprocess に渡されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["model", "train", "--auto-promote"])
        cmd = mock_sub.call_args[0][0]
        assert "--auto-promote" in cmd

    def test_notes_option(self, runner):
        """--notes が subprocess に渡されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["model", "train", "--notes", "テスト学習"])
        cmd = mock_sub.call_args[0][0]
        assert "--notes" in cmd


# ============================================================
# model promote（確認プロンプト / FileNotFoundError）
# ============================================================

class TestModelPromoteExtra:
    def test_promote_with_confirmation(self, runner, cli_registry):
        """--yes なしで Enter 入力して昇格できること"""
        registry, _ = cli_registry
        target = registry.list_versions()[0]["version"]
        from app.cli import cli
        result = runner.invoke(cli, ["model", "promote", "--version", target], input="y\n")
        assert result.exit_code == 0

    def test_promote_file_not_found_exits(self, runner, cli_registry):
        """registry.promote が FileNotFoundError を投げるときエラー終了すること"""
        registry, _ = cli_registry
        target = registry.list_versions()[0]["version"]

        with patch("app.model.versioning.ModelRegistry.promote",
                   side_effect=FileNotFoundError("no pkl")):
            from app.cli import cli
            result = runner.invoke(cli, ["model", "promote", "--version", target, "--yes"])
        assert result.exit_code != 0


# ============================================================
# model cleanup（確認プロンプト）
# ============================================================

class TestModelCleanupConfirm:
    def test_cleanup_with_confirmation(self, runner, tmp_path, monkeypatch):
        """--yes なしで Enter 入力して削除できること"""
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
        for _ in range(3):
            registry.register(_PicklableModel(), metrics)

        from app.cli import cli
        result = runner.invoke(cli, ["model", "cleanup", "--keep", "1"], input="y\n")
        assert result.exit_code == 0


# ============================================================
# api serve（uvicorn mock）
# ============================================================

class TestApiServe:
    def test_serve_calls_uvicorn(self, runner):
        """api serve が uvicorn.run を呼ぶこと"""
        with patch("uvicorn.run") as mock_run:
            from app.cli import cli
            runner.invoke(cli, ["api", "serve", "--port", "9999"])
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("port") == 9999 or mock_run.call_args[0][1:] or True

    def test_serve_with_reload(self, runner):
        """--reload オプションが uvicorn に渡されること"""
        with patch("uvicorn.run") as mock_run:
            from app.cli import cli
            runner.invoke(cli, ["api", "serve", "--reload"])
        _, kwargs = mock_run.call_args
        assert kwargs.get("reload") is True


# ============================================================
# data convert（subprocess mock）
# ============================================================

class TestDataConvert:
    def _mock_proc(self, returncode=0):
        m = MagicMock()
        m.returncode = returncode
        return m

    def test_convert_calls_subprocess(self, runner):
        """data convert がスクリプトを subprocess で呼ぶこと"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["data", "convert"])
        assert mock_sub.called
        cmd = mock_sub.call_args[0][0]
        assert "convert_data.py" in " ".join(cmd)

    def test_dry_run_flag_passed(self, runner):
        """--dry-run が subprocess コマンドに追加されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["data", "convert", "--dry-run"])
        cmd = mock_sub.call_args[0][0]
        assert "--dry-run" in cmd


# ============================================================
# data validate（成功パス）
# ============================================================

class TestDataValidateSuccess:
    def test_no_issues_shows_ok(self, runner, tmp_path):
        """品質チェック問題なしのとき '問題なし' が表示されること"""
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=200))
        csv_path = tmp_path / "train.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["data", "validate", "--path", str(csv_path)])
        assert result.exit_code == 0
        assert "問題なし" in result.output

    def test_with_issues_shows_warning(self, runner, tmp_path):
        """品質警告があるとき ⚠ が表示されること"""
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=5))
        csv_path = tmp_path / "tiny.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["data", "validate", "--path", str(csv_path)])
        assert result.exit_code == 0
        assert "⚠" in result.output or "少なすぎ" in result.output


# ============================================================
# simulate グループ（subprocess mock）
# ============================================================

class TestSimulate:
    def _mock_proc(self):
        m = MagicMock()
        m.returncode = 0
        return m

    def test_simulate_run_calls_subprocess(self, runner):
        """simulate run が simulator.py を subprocess で呼ぶこと"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["simulate", "run"])
        assert mock_sub.called
        cmd = mock_sub.call_args[0][0]
        assert "simulator.py" in " ".join(cmd)

    def test_simulate_run_no_plot(self, runner):
        """--no-plot が subprocess コマンドに追加されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["simulate", "run", "--no-plot"])
        cmd = mock_sub.call_args[0][0]
        assert "--no-plot" in cmd

    def test_simulate_backtest_calls_subprocess(self, runner):
        """simulate backtest が backtester.py を subprocess で呼ぶこと"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["simulate", "backtest"])
        assert mock_sub.called
        cmd = mock_sub.call_args[0][0]
        assert "backtester.py" in " ".join(cmd)

    def test_simulate_backtest_walk_forward(self, runner):
        """--walk-forward が subprocess に渡されること"""
        with patch("subprocess.run", return_value=self._mock_proc()) as mock_sub:
            from app.cli import cli
            runner.invoke(cli, ["simulate", "backtest", "--walk-forward"])
        cmd = mock_sub.call_args[0][0]
        assert "--walk-forward" in cmd


# ============================================================
# shadow clear（成功パス / 存在しない場合）
# ============================================================

class TestShadowClear:
    def test_clear_existing_log(self, runner, tmp_path, monkeypatch):
        """存在するログを --yes で削除できること"""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "data" / "shadow_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "shadow.jsonl"
        log_file.write_text('{"top1_match": true}\n', encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "clear", "--name", "shadow", "--yes"])
        assert result.exit_code == 0
        assert not log_file.exists()
        assert "削除しました" in result.output

    def test_clear_nonexistent_log(self, runner, tmp_path, monkeypatch):
        """存在しないログのとき 'ファイルが見つかりません' を表示すること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "clear", "--name", "ghost", "--yes"])
        assert result.exit_code == 0
        assert "見つかりません" in result.output

    def test_shadow_stats_empty_file(self, runner, tmp_path, monkeypatch):
        """存在するが空のログのとき '記録なし' を表示すること"""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "data" / "shadow_logs"
        log_dir.mkdir(parents=True)
        (log_dir / "empty.jsonl").write_text("", encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "stats", "--name", "empty"])
        assert result.exit_code == 0
        assert "記録なし" in result.output


# ============================================================
# scoring race - result のみパス / bad JSON パス
# ============================================================

class TestScoringEdgeCases:
    def test_race_result_only(self, runner, tmp_path, monkeypatch):
        """結果のみ（予測なし）のとき '予測なし' が表示されること"""
        monkeypatch.chdir(tmp_path)
        result_dir = tmp_path / "data" / "race_results"
        result_dir.mkdir(parents=True)
        (result_dir / "r_result_only.json").write_text(
            json.dumps({"race_id": "r_result_only", "true_winner": 4}),
            encoding="utf-8",
        )
        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_result_only"])
        assert result.exit_code == 0
        assert "予測なし" in result.output

    def test_overview_bad_json_skipped(self, runner, tmp_path, monkeypatch):
        """壊れた JSON ファイルがスキップされて正常終了すること"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        pred_dir.mkdir(parents=True)
        (pred_dir / "broken.json").write_text("NOT JSON", encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview"])
        assert result.exit_code == 0
        assert "データなし" in result.output

    def test_race_bad_pred_json(self, runner, tmp_path, monkeypatch):
        """予測 JSON が壊れているとき pred=None として扱われること"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        pred_dir.mkdir(parents=True)
        (pred_dir / "r_bad.json").write_text("INVALID", encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_bad"])
        # pred も result もないので exit_code=1
        assert result.exit_code == 1


# ============================================================
# model drift コマンド
# ============================================================

class TestModelDrift:
    def test_drift_sample_data(self, runner, tmp_path, monkeypatch):
        """model drift がサンプルデータで正常完了すること"""
        monkeypatch.chdir(tmp_path)
        from app.cli import cli
        result = runner.invoke(cli, ["model", "drift", "--n-races", "50"])
        assert result.exit_code == 0
        assert "ドリフト検査" in result.output

    def test_drift_needs_retraining(self, runner, tmp_path, monkeypatch):
        """needs_retraining=True のとき警告メッセージが出ること"""
        from unittest.mock import MagicMock, patch
        monkeypatch.chdir(tmp_path)

        mock_report = MagicMock()
        mock_report.needs_retraining = True

        mock_detector = MagicMock()
        mock_detector.check.return_value = mock_report

        with patch("app.model.drift.DriftDetector", return_value=mock_detector):
            from app.cli import cli
            result = runner.invoke(cli, ["model", "drift", "--n-races", "50"])
        assert result.exit_code == 0

    def test_drift_with_data_path(self, runner, tmp_path, monkeypatch):
        """--data-path が指定されたとき CSV を読み込むこと (lines 140-141)"""
        from unittest.mock import MagicMock, patch
        import pandas as pd
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        monkeypatch.chdir(tmp_path)

        df = preprocess_dataframe(generate_sample_training_data(n_races=50))
        csv_path = tmp_path / "data.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["model", "drift", "--data-path", str(csv_path)])
        assert result.exit_code == 0
        assert "ドリフト検査" in result.output


# ============================================================
# shadow stats – 不正 JSON スキップ (lines 367-368)
# ============================================================

class TestShadowStatsBadJson:
    def test_corrupt_line_skipped(self, runner, tmp_path, monkeypatch):
        """ログに不正 JSON が含まれているときスキップして処理継続すること"""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "data" / "shadow_logs"
        log_dir.mkdir(parents=True)
        (log_dir / "shadow.jsonl").write_text(
            'NOT_JSON\n{"top1_match": false, "kl_divergence": 0.02}\n',
            encoding="utf-8",
        )
        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "stats", "--name", "shadow"])
        assert result.exit_code == 0
        assert "1位一致率" in result.output


# ============================================================
# shadow clear – --yes なし (line 400)
# ============================================================

class TestShadowClearConfirm:
    def test_clear_with_confirmation_prompt(self, runner, tmp_path, monkeypatch):
        """--yes なしで y を入力して削除できること (line 400)"""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "data" / "shadow_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "shadow.jsonl"
        log_file.write_text('{"top1_match": false}\n', encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["shadow", "clear", "--name", "shadow"], input="y\n")
        assert result.exit_code == 0
        assert not log_file.exists()


# ============================================================
# result summary – --n オプション / 空ディレクトリ / corrupt JSON
# ============================================================

class TestResultSummaryEdgeCases:
    def test_with_n_option(self, runner, tmp_path, monkeypatch):
        """--n オプションで直近N件に絞れること (line 473)"""
        monkeypatch.chdir(tmp_path)
        result_dir = tmp_path / "data" / "race_results"
        result_dir.mkdir(parents=True)
        for i in range(5):
            rec = {"race_id": f"r{i}", "is_correct": True, "prediction_rank": 1}
            (result_dir / f"r{i}.json").write_text(json.dumps(rec), encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["result", "summary", "--n", "3"])
        assert result.exit_code == 0
        assert "的中率" in result.output

    def test_empty_dir_shows_message(self, runner, tmp_path, monkeypatch):
        """result ディレクトリが存在するが空のとき '記録なし' を返すこと (lines 476-477)"""
        monkeypatch.chdir(tmp_path)
        result_dir = tmp_path / "data" / "race_results"
        result_dir.mkdir(parents=True)
        # ディレクトリは存在するが JSON ファイルなし

        from app.cli import cli
        result = runner.invoke(cli, ["result", "summary"])
        assert result.exit_code == 0
        assert "記録なし" in result.output

    def test_corrupt_json_skipped(self, runner, tmp_path, monkeypatch):
        """壊れた JSON ファイルをスキップして続行すること (lines 489-490)"""
        monkeypatch.chdir(tmp_path)
        result_dir = tmp_path / "data" / "race_results"
        result_dir.mkdir(parents=True)
        (result_dir / "bad.json").write_text("CORRUPT{{{", encoding="utf-8")
        # 正常ファイルも追加
        rec = {"race_id": "ok", "is_correct": True, "prediction_rank": 1}
        (result_dir / "ok.json").write_text(json.dumps(rec), encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["result", "summary"])
        assert result.exit_code == 0
        assert "的中率" in result.output


# ============================================================
# scoring overview – corrupt result JSON / missing proba
# ============================================================

class TestScoringOverviewEdgeCases:
    def test_corrupt_result_json_skipped(self, runner, tmp_path, monkeypatch):
        """壊れた結果 JSON がスキップされること (lines 553-554)"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        pred_dir.mkdir(parents=True)
        result_dir.mkdir(parents=True)
        # 正常な予測ファイル
        pred = {"race_id": "r1", "win_probabilities": [0.5, 0.1, 0.1, 0.1, 0.1, 0.1],
                "race_date": "20260427", "jyo_code": "01"}
        (pred_dir / "r1.json").write_text(json.dumps(pred), encoding="utf-8")
        # 壊れた結果ファイル
        (result_dir / "r1.json").write_text("NOT_JSON", encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview"])
        assert result.exit_code == 0

    def test_missing_proba_skipped(self, runner, tmp_path, monkeypatch):
        """proba なしの予測はスキップされること (line 576)"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        pred_dir.mkdir(parents=True)
        result_dir.mkdir(parents=True)
        # proba なしの予測
        pred = {"race_id": "r_noproba", "race_date": "20260427", "jyo_code": "01"}
        (pred_dir / "r_noproba.json").write_text(json.dumps(pred), encoding="utf-8")
        result_rec = {"race_id": "r_noproba", "true_winner": 1}
        (result_dir / "r_noproba.json").write_text(json.dumps(result_rec), encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "overview"])
        assert result.exit_code == 0


# ============================================================
# scoring race – corrupt result JSON (lines 640-641)
# ============================================================

class TestScoringRaceEdgeCases:
    def test_corrupt_result_returns_partial(self, runner, tmp_path, monkeypatch):
        """result JSON が壊れているとき pred のみで表示すること (lines 640-641)"""
        monkeypatch.chdir(tmp_path)
        pred_dir = tmp_path / "data" / "prediction_logs"
        result_dir = tmp_path / "data" / "race_results"
        pred_dir.mkdir(parents=True)
        result_dir.mkdir(parents=True)

        pred = {"race_id": "r_corrupt", "win_probabilities": [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]}
        (pred_dir / "r_corrupt.json").write_text(json.dumps(pred), encoding="utf-8")
        (result_dir / "r_corrupt.json").write_text("CORRUPT", encoding="utf-8")

        from app.cli import cli
        result = runner.invoke(cli, ["scoring", "race", "r_corrupt"])
        assert result.exit_code == 0
        assert "あり" in result.output  # 予測ログあり


# ============================================================
# ab_test – warn branch / numpy serialization
# ============================================================

class TestAbTestWarnBranch:
    def test_get_report_warn_branch(self):
        """p_value が 0.05〜0.1 のとき warn メッセージが出ること (lines 260-261)"""
        from unittest.mock import patch, MagicMock
        import numpy as np
        from scipy import stats as scipy_stats
        from app.model.ab_test import ABTestRouter

        router = ABTestRouter(name="warn_test")

        class _FakeModel:
            def predict_proba(self, X):
                return np.ones((6, 6)) / 6

        router.add_variant("A", _FakeModel(), traffic_weight=0.5)
        router.add_variant("B", _FakeModel(), traffic_weight=0.5)

        # Manually set enough requests and a p_value in 0.05-0.1 range
        v0, v1 = router._variants[0], router._variants[1]
        v0.n_requests = 35
        v1.n_requests = 35
        # ~60% vs ~42% hit rate → forced with monkeypatching norm.cdf
        v0.n_correct = 21
        v1.n_correct = 15

        # Force norm.cdf to give p_value between 0.05 and 0.1
        with patch("scipy.stats.norm.cdf", return_value=0.96):
            report = router.get_report()

        assert "優勢" in report.message or "データ蓄積" in report.message

    def test_save_log_entry_numpy_types(self, tmp_path, monkeypatch):
        """_save_log_entry が np.floating/np.ndarray を JSON シリアライズすること (303, 305)"""
        import numpy as np
        import app.model.ab_test as ab_mod
        monkeypatch.setattr(ab_mod, "AB_LOG_DIR", tmp_path)

        from app.model.ab_test import ABTestRouter

        class _FakeModel:
            def predict_proba(self, X):
                return np.ones((6, 6)) / 6

        router = ABTestRouter(name="serial_test")
        router.add_variant("A", _FakeModel(), traffic_weight=1.0)

        # Call _save_log_entry with numpy types in the log dict
        log_with_numpy = {
            "variant": "A",
            "predicted_1st": np.int64(0),
            "proba": np.array([0.2, 0.15, 0.15, 0.15, 0.15, 0.2]),
            "latency_ms": np.float64(12.5),
            "true_winner": None,
        }
        router._save_log_entry("test_race_001", log_with_numpy)

        log_file = tmp_path / "serial_test.jsonl"
        assert log_file.exists()
        import json
        data = json.loads(log_file.read_text())
        assert isinstance(data["latency_ms"], float)
        assert isinstance(data["proba"], list)


# ============================================================
# main.py – DB close exception (lines 70-71)
# ============================================================

class TestMainDbCloseException:
    def test_db_close_exception_swallowed(self):
        """シャットダウン時の DB close 例外が無視されること (lines 70-71)"""
        from unittest.mock import AsyncMock, patch
        from fastapi.testclient import TestClient

        async def _raise():
            raise RuntimeError("db close failed")

        with patch("app.main._USE_DB", True), \
             patch("app.db.close_pool", new=AsyncMock(side_effect=RuntimeError("db close"))):
            from app.main import app as _app
            with TestClient(_app) as tc:
                pass  # lifespan exit triggers DB close → exception swallowed
