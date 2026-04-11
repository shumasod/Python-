"""
競艇予想AI 管理CLI
Click ベースのコマンドラインインターフェース

インストール:
  pip install click

使い方:
  python -m app.cli --help
  python -m app.cli model list
  python -m app.cli model promote --latest
  python -m app.cli model drift --n-races 500
  python -m app.cli api keygen
  python -m app.cli api health
  python -m app.cli data convert
  python -m app.cli data validate

エイリアス設定（任意）:
  alias boat-race="python -m app.cli"
  boat-race model list
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import click
except ImportError:
    print("click が未インストールです。pip install click を実行してください。")
    sys.exit(1)


# ============================================================
# グループ定義
# ============================================================

@click.group()
@click.version_option(version="1.0.0", prog_name="boat-race-ai")
def cli():
    """競艇予想AI 管理コマンド"""
    pass


# ============================================================
# model グループ
# ============================================================

@cli.group()
def model():
    """モデル管理コマンド"""
    pass


@model.command("list")
def model_list():
    """登録済みモデルバージョン一覧を表示する"""
    from app.model.versioning import ModelRegistry
    registry = ModelRegistry()
    registry.print_summary()


@model.command("promote")
@click.option("--version", "-v", default=None, help="昇格するバージョン名")
@click.option("--latest", is_flag=True, help="最新バージョンを昇格")
@click.option("--yes", "-y", is_flag=True, help="確認プロンプトをスキップ")
def model_promote(version, latest, yes):
    """モデルバージョンを本番に昇格する"""
    from app.model.versioning import ModelRegistry

    registry = ModelRegistry()
    versions = registry.list_versions()

    if latest:
        if not versions:
            click.echo("登録済みバージョンがありません", err=True)
            sys.exit(1)
        target = versions[-1]["version"]
    elif version:
        target = version
    else:
        click.echo("--version または --latest を指定してください", err=True)
        sys.exit(1)

    current = registry.get_production_version()
    click.echo(f"現在の本番: {current or 'なし'}")
    click.echo(f"昇格対象  : {target}")

    if not yes:
        click.confirm("本番モデルを更新しますか？", abort=True)

    try:
        registry.promote(target)
        click.secho(f"✓ 本番モデルを更新しました: {target}", fg="green")
    except FileNotFoundError as e:
        click.secho(f"エラー: {e}", fg="red", err=True)
        sys.exit(1)


@model.command("train")
@click.option("--n-races", default=2000, help="サンプルレース数")
@click.option("--data-path", default=None, help="学習データCSVパス")
@click.option("--auto-promote", is_flag=True, help="学習後に自動昇格")
@click.option("--notes", default="", help="バージョン備考")
def model_train(n_races, data_path, auto_promote, notes):
    """モデルを学習してバージョン登録する"""
    import subprocess
    cmd = [sys.executable, "scripts/train_model.py"]
    if data_path:
        cmd += ["--data-path", data_path]
    else:
        cmd += ["--use-sample", "--n-races", str(n_races)]
    if auto_promote:
        cmd.append("--auto-promote")
    if notes:
        cmd += ["--notes", notes]

    click.echo(f"実行: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


@model.command("drift")
@click.option("--n-races", default=500, help="テスト用サンプルレース数")
@click.option("--data-path", default=None, help="本番データCSVパス")
def model_drift(n_races, data_path):
    """モデルドリフトを検査する"""
    from app.model.drift import DriftDetector
    from app.model.features import generate_sample_training_data, preprocess_dataframe

    click.echo("ドリフト検査を実行します...")
    detector = DriftDetector()

    # 参照分布を設定
    ref_df = preprocess_dataframe(generate_sample_training_data(n_races=2000))
    detector.set_reference(ref_df)

    # 現在データ
    if data_path:
        from app.data.loader import load_training_data
        current_df = load_training_data(file_path=data_path)
    else:
        current_df = preprocess_dataframe(generate_sample_training_data(n_races=n_races))

    report = detector.check(current_df)
    detector.print_report(report)

    if report.needs_retraining:
        click.secho("\n⚠ 再学習を推奨します: make train-register", fg="yellow")
    else:
        click.secho("\n✓ モデルは安定しています", fg="green")


@model.command("cleanup")
@click.option("--keep", default=10, help="保持するバージョン数")
@click.option("--yes", "-y", is_flag=True, help="確認プロンプトをスキップ")
def model_cleanup(keep, yes):
    """古いモデルバージョンを削除する"""
    from app.model.versioning import ModelRegistry
    registry = ModelRegistry()

    versions = registry.list_versions()
    to_delete = max(0, len(versions) - keep)
    click.echo(f"登録数: {len(versions)}  削除予定: {to_delete}")

    if to_delete == 0:
        click.echo("削除対象なし")
        return

    if not yes:
        click.confirm(f"{to_delete} バージョンを削除しますか？", abort=True)

    deleted = registry.cleanup_old_versions(keep=keep)
    click.secho(f"✓ {deleted} ファイルを削除しました", fg="green")


# ============================================================
# api グループ
# ============================================================

@cli.group()
def api():
    """APIサーバー管理コマンド"""
    pass


@api.command("keygen")
@click.option("--prefix", default="br", help="キーのプレフィックス")
@click.option("--count", default=1, help="生成する件数")
def api_keygen(prefix, count):
    """新しいAPIキーを生成する"""
    from app.api.auth import generate_api_key
    click.echo("生成した API Key（API_KEYS 環境変数に追加してください）:")
    for _ in range(count):
        key = generate_api_key(prefix)
        click.secho(f"  {key}", fg="cyan")


@api.command("health")
@click.option("--url", default="http://localhost:8000", help="APIサーバーのURL")
def api_health(url):
    """APIサーバーのヘルス状態を確認する"""
    import requests
    try:
        resp = requests.get(f"{url}/health/detail", timeout=5)
        data = resp.json()
        status = data.get("status", "unknown")
        color = "green" if status == "ok" else "yellow" if status == "degraded" else "red"
        click.secho(f"ステータス: {status}", fg=color)
        click.echo(f"稼働時間: {data.get('uptime_sec', 0)} 秒")

        for name, check in data.get("checks", {}).items():
            s = check.get("status", "?")
            icon = "✓" if s == "ok" else "△" if s in ("warn", "disabled") else "✗"
            click.echo(f"  {icon} {name}: {s}")
    except Exception as e:
        click.secho(f"接続失敗: {e}", fg="red", err=True)
        sys.exit(1)


@api.command("serve")
@click.option("--host", default="0.0.0.0", help="バインドホスト")
@click.option("--port", default=8000, help="ポート番号")
@click.option("--reload", is_flag=True, help="開発モード（自動リロード）")
def api_serve(host, port, reload):
    """APIサーバーを起動する"""
    import uvicorn
    click.echo(f"APIサーバーを起動します: http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )


# ============================================================
# data グループ
# ============================================================

@cli.group()
def data():
    """データ管理コマンド"""
    pass


@data.command("convert")
@click.option("--input-dir", default="data/scraped", help="スクレイピングデータのディレクトリ")
@click.option("--output", default="data/training.csv", help="出力CSVパス")
@click.option("--dry-run", is_flag=True, help="サマリーのみ表示")
def data_convert(input_dir, output, dry_run):
    """スクレイピングデータを学習用CSVに変換する"""
    import subprocess
    cmd = [
        sys.executable, "scripts/convert_data.py",
        "--input-dir", input_dir,
        "--output", output,
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


@data.command("validate")
@click.option("--path", default="data/training.csv", help="検証するCSVパス")
def data_validate(path):
    """学習データの品質チェックを実行する"""
    from scripts.convert_data import validate_training_data
    import pandas as pd

    p = Path(path)
    if not p.exists():
        click.secho(f"ファイルが見つかりません: {path}", fg="red", err=True)
        sys.exit(1)

    df = pd.read_csv(p, encoding="utf-8")
    result = validate_training_data(df)

    click.echo(f"行数    : {result['n_rows']:,}")
    click.echo(f"レース数: {result['n_races']:,}")

    if result["issues"]:
        for issue in result["issues"]:
            click.secho(f"⚠ {issue}", fg="yellow")
    else:
        click.secho("✓ 品質チェック問題なし", fg="green")


# ============================================================
# simulate グループ
# ============================================================

@cli.group()
def simulate():
    """シミュレーション・バックテストコマンド"""
    pass


@simulate.command("run")
@click.option("--n-races", default=200, help="シミュレーションするレース数")
@click.option("--ev-threshold", default=1.0, help="期待値閾値")
@click.option("--kelly-frac", default=0.5, help="ケリー係数")
@click.option("--no-plot", is_flag=True, help="グラフを表示しない")
def simulate_run(n_races, ev_threshold, kelly_frac, no_plot):
    """回収率シミュレーションを実行する"""
    import subprocess
    cmd = [
        sys.executable, "simulator.py",
        "--n-races", str(n_races),
        "--ev-threshold", str(ev_threshold),
        "--kelly-frac", str(kelly_frac),
    ]
    if no_plot:
        cmd.append("--no-plot")
    subprocess.run(cmd, check=False)


@simulate.command("backtest")
@click.option("--n-races", default=500, help="バックテストレース数")
@click.option("--walk-forward", is_flag=True, help="ウォークフォワード検証")
@click.option("--ev-threshold", default=1.0, help="期待値閾値")
def simulate_backtest(n_races, walk_forward, ev_threshold):
    """バックテストを実行する"""
    import subprocess
    cmd = [
        sys.executable, "backtester.py",
        "--n-races", str(n_races),
        "--ev-threshold", str(ev_threshold),
        "--no-plot",
    ]
    if walk_forward:
        cmd.append("--walk-forward")
    subprocess.run(cmd, check=False)


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":
    cli()
