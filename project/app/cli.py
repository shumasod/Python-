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

from app.config import PREDICTION_LOG_DIR, RESULT_LOG_DIR, SHADOW_LOG_DIR

try:
    import click
except ImportError:  # pragma: no cover
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
    import pandas as pd
    from scripts.convert_data import validate_training_data

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
# shadow グループ（シャドウモード管理）
# ============================================================

@cli.group()
def shadow():
    """シャドウモード管理コマンド"""
    pass


@shadow.command("stats")
@click.option("--name", default="shadow", help="シャドウログ名（data/shadow_logs/<name>.jsonl）")
def shadow_stats(name):
    """シャドウモードの累積統計を表示する"""
    from app.api.admin import _read_shadow_stats
    stats = _read_shadow_stats(name)

    if stats["n_sampled"] == 0:
        click.echo("記録なし")
        return

    n  = stats["n_sampled"]
    mr = stats["top1_match_rate"] or 0.0
    kl = stats["avg_kl_divergence"] or 0.0
    click.echo(f"\n{'='*50}")
    click.echo(f" シャドウモード統計: {name}")
    click.echo(f"{'='*50}")
    click.echo(f" サンプル数  : {n}")
    click.echo(f" 1位一致率   : {mr*100:.1f}%")
    click.echo(f" 平均KL距離  : {kl:.6f}")
    click.echo("=" * 50)


@shadow.command("clear")
@click.option("--name", default="shadow", help="シャドウログ名")
@click.option("--yes", "-y", is_flag=True, help="確認プロンプトをスキップ")
def shadow_clear(name, yes):
    """シャドウモードのログをクリアする"""

    log_path = SHADOW_LOG_DIR / f"{name}.jsonl"
    if not log_path.exists():
        click.echo(f"ログファイルが見つかりません: {log_path}")
        return

    if not yes:
        click.confirm(f"{log_path} を削除しますか？", abort=True)

    log_path.unlink()
    click.echo(f"削除しました: {log_path}")


# ============================================================
# result グループ（レース結果管理）
# ============================================================

@cli.group()
def result():
    """レース結果管理コマンド"""
    pass


@result.command("record")
@click.argument("race_id")
@click.argument("winner", type=click.IntRange(1, 6))
@click.option("--second", type=click.IntRange(1, 6), default=None, help="2着艇番")
@click.option("--third", type=click.IntRange(1, 6), default=None, help="3着艇番")
@click.option("--note", default=None, help="備考")
def result_record(race_id, winner, second, third, note):
    """レース結果を記録する

    \b
    例:
      python -m app.cli result record race_20240415_01 3
      python -m app.cli result record race_20240415_01 3 --second 1 --third 5
    """
    import json

    result_dir = RESULT_LOG_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    path = result_dir / f"{race_id}.json"

    if path.exists():
        click.echo(f"エラー: {race_id} の結果は既に記録されています", err=True)
        sys.exit(1)

    from datetime import datetime, timezone
    record = {
        "race_id": race_id,
        "true_winner": winner,
        "second_place": second,
        "third_place": third,
        "note": note,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "predicted_winner": None,
        "is_correct": None,
        "prediction_rank": None,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    click.echo(f"記録完了: {race_id} → 1着: {winner}号艇")


@result.command("summary")
@click.option("--n", default=None, type=int, help="直近N件のみ集計")
def result_summary(n):
    """的中率サマリーを表示する"""
    import json

    result_dir = RESULT_LOG_DIR
    if not result_dir.exists():
        click.echo("記録なし")
        return

    files = sorted(result_dir.glob("*.json"))
    if n:
        files = files[-n:]

    if not files:
        click.echo("記録なし")
        return

    total = 0
    correct = 0
    rank_sum = 0.0
    n_with_rank = 0
    top3 = 0

    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        total += 1
        if rec.get("is_correct"):
            correct += 1
        pred_rank = rec.get("prediction_rank")
        if pred_rank is not None:
            rank_sum += pred_rank
            n_with_rank += 1
            if pred_rank <= 3:
                top3 += 1

    hit_rate = correct / total if total else 0
    top3_rate = top3 / n_with_rank if n_with_rank else 0
    avg_rank = rank_sum / n_with_rank if n_with_rank else 0

    label = f"直近{n}件" if n else "全件"
    click.echo(f"\n{'='*50}")
    click.echo(f" 予測精度サマリー ({label})")
    click.echo(f"{'='*50}")
    click.echo(f" 記録数     : {total}")
    click.echo(f" 1着的中率  : {hit_rate*100:.1f}%")
    click.echo(f" Top-3率    : {top3_rate*100:.1f}%")
    click.echo(f" 平均予測順位: {avg_rank:.2f}")
    click.echo("=" * 50)


# ============================================================
# scoring グループ（予測スコアリング）
# ============================================================

@cli.group()
def scoring():
    """予測スコアリング管理コマンド"""
    pass


@scoring.command("overview")
@click.option("--date", default=None, help="集計対象日 (YYYYMMDD)")
@click.option("--venue", "-v", default=None, help="場コードでフィルター (01〜24)")
def scoring_overview(date, venue):
    """予測と実結果を突き合わせた的中率概要を表示する"""
    from app.api.scoring import _agg, _collect_scores

    all_scores = _collect_scores()

    if date:
        all_scores = [s for s in all_scores if s.race_date == date]
    if venue:
        all_scores = [s for s in all_scores if s.jyo_code == venue]

    scored = [s for s in all_scores if s.has_prediction and s.has_result]
    if not scored:
        click.echo("集計対象データなし")
        return

    agg         = _agg(scored)
    n           = len(scored)
    n_correct   = agg["n_correct"]
    n_with_rank = sum(1 for s in scored if s.prediction_rank is not None)
    top3        = sum(1 for s in scored if s.prediction_rank is not None and s.prediction_rank <= 3)
    rank_sum    = sum(s.prediction_rank for s in scored if s.prediction_rank is not None)

    filter_str = ""
    if date:
        filter_str += f"  日付: {date}"
    if venue:
        filter_str += f"  場: {venue}"

    n_preds   = sum(1 for s in all_scores if s.has_prediction)
    n_results = sum(1 for s in all_scores if s.has_result)

    click.echo(f"\n{'='*50}")
    click.echo(" 予測スコアリング概要" + (f" [{filter_str.strip()}]" if filter_str else ""))
    click.echo(f"{'='*50}")
    click.echo(f" 予測ログ数  : {n_preds}")
    click.echo(f" 結果ログ数  : {n_results}")
    click.echo(f" 突き合わせ数: {n}")
    click.echo(f" 的中数      : {n_correct}")
    click.echo(f" 1着的中率   : {n_correct/n*100:.1f}%" if n else " 1着的中率   : N/A")
    click.echo(f" Top-3率     : {top3/n_with_rank*100:.1f}%" if n_with_rank else " Top-3率     : N/A")
    click.echo(f" 平均予測順位: {rank_sum/n_with_rank:.2f}" if n_with_rank else " 平均予測順位: N/A")
    click.echo("=" * 50)


@scoring.command("race")
@click.argument("race_id")
def scoring_race(race_id):
    """指定レースの予測と実結果を表示する

    \b
    例:
      python -m app.cli scoring race 20260420_01_R01
    """
    import numpy as np

    from app.api.scoring import _load_json, _rank_proba

    pred_path   = PREDICTION_LOG_DIR / f"{race_id}.json"
    result_path = RESULT_LOG_DIR     / f"{race_id}.json"

    pred   = _load_json(pred_path)   if pred_path.exists()   else None
    result = _load_json(result_path) if result_path.exists() else None

    if pred is None and result is None:
        click.secho(f"レースID {race_id} の予測も結果も見つかりません", fg="red", err=True)
        sys.exit(1)

    click.echo(f"\n{'='*50}")
    click.echo(f" レース: {race_id}")
    click.echo(f"{'='*50}")
    click.echo(f" 予測ログ: {'あり' if pred else 'なし'}")
    click.echo(f" 結果ログ: {'あり' if result else 'なし'}")

    if pred and result:
        proba       = pred.get("win_probabilities") or pred.get("proba") or []
        true_winner = result.get("true_winner")
        if proba and true_winner is not None:
            ranked     = _rank_proba(proba, true_winner)
            predicted  = ranked["predicted_winner"]
            is_correct = ranked["is_correct"]
            rank       = ranked["prediction_rank"]
            arr        = np.array(proba)
            click.echo(f" 予測1位   : {predicted}号艇  (確率: {arr[predicted-1]*100:.1f}%)")
            click.echo(f" 実際の1着 : {true_winner}号艇")
            if rank:
                click.echo(f" 正解艇の予測順位: {rank}位")
            color = "green" if is_correct else "red"
            label = "✓ 的中" if is_correct else "✗ 外れ"
            click.secho(f" 結果      : {label}", fg=color)
    elif pred:
        proba = pred.get("win_probabilities") or pred.get("proba") or []
        if proba:
            arr   = np.array(proba)
            order = arr.argsort()[::-1]
            click.echo(f" 予測1位   : {int(order[0])+1}号艇  (確率: {arr[order[0]]*100:.1f}%)")
        click.echo(" 結果未記録")
    elif result:
        click.echo(f" 実際の1着 : {result.get('true_winner')}号艇")
        click.echo(" 予測なし")

    click.echo("=" * 50)


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":  # pragma: no cover
    cli()
