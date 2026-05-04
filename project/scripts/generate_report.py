"""
週次パフォーマンスレポート生成スクリプト
モデル精度・回収率・ドリフト状況をまとめた HTML レポートを生成する

実行例:
  python scripts/generate_report.py
  python scripts/generate_report.py --out output/report --days 30
  python scripts/generate_report.py --format html  # HTMLのみ生成
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# データ収集
# ============================================================

def collect_prediction_accuracy(result_dir: Path, days: int) -> Dict[str, Any]:
    """直近 N 日間のレース結果から的中率を集計する"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    correct = 0
    rank_sum = 0.0
    n_with_rank = 0
    top3 = 0
    daily: Dict[str, Dict] = {}

    for p in result_dir.glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # 期間フィルター
        recorded_at_str = rec.get("recorded_at", "")
        if recorded_at_str:
            try:
                recorded_at = datetime.fromisoformat(recorded_at_str)
                if recorded_at < cutoff:
                    continue
                day_key = recorded_at.strftime("%Y-%m-%d")
            except ValueError:
                day_key = "unknown"
        else:
            day_key = "unknown"

        total += 1
        is_correct = rec.get("is_correct", False)
        if is_correct:
            correct += 1

        pred_rank = rec.get("prediction_rank")
        if pred_rank is not None:
            rank_sum += pred_rank
            n_with_rank += 1
            if pred_rank <= 3:
                top3 += 1

        if day_key not in daily:
            daily[day_key] = {"total": 0, "correct": 0}
        daily[day_key]["total"] += 1
        if is_correct:
            daily[day_key]["correct"] += 1

    return {
        "n_results": total,
        "hit_rate": round(correct / total, 4) if total else 0.0,
        "top3_rate": round(top3 / n_with_rank, 4) if n_with_rank else 0.0,
        "avg_prediction_rank": round(rank_sum / n_with_rank, 2) if n_with_rank else 0.0,
        "daily": daily,
    }


def collect_model_versions() -> List[Dict[str, Any]]:
    """登録済みモデルバージョンの一覧を取得する"""
    try:
        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        versions = registry.list_versions()
        prod = registry.get_production_version()
        for v in versions:
            v["is_production"] = (v["version"] == prod)
        return versions
    except Exception as e:
        logger.warning(f"モデルバージョン取得失敗: {e}")
        return []


def collect_drift_reports(drift_dir: Path, n: int = 7) -> List[Dict[str, Any]]:
    """最新 N 件のドリフトレポートを取得する"""
    reports = sorted(drift_dir.glob("*.json"))[-n:]
    result = []
    for p in reports:
        try:
            with open(p, encoding="utf-8") as f:
                result.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return result


def collect_ab_test_summary(ab_dir: Path) -> List[Dict[str, Any]]:
    """A/B テストログのサマリーを収集する"""
    summaries = []
    for log_file in ab_dir.glob("*.jsonl"):
        n = 0
        variants: Dict[str, Dict] = {}
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                v = entry.get("variant", "unknown")
                if v not in variants:
                    variants[v] = {"n": 0}
                variants[v]["n"] += 1
                n += 1
        summaries.append({
            "name": log_file.stem,
            "n_total": n,
            "variants": variants,
        })
    return summaries


def collect_shadow_stats(shadow_dir: Path) -> List[Dict[str, Any]]:
    """シャドウモードの統計を収集する"""
    results = []
    for log_file in shadow_dir.glob("*.jsonl"):
        n = n_match = 0
        kl_sum = 0.0
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                n += 1
                if entry.get("top1_match"):
                    n_match += 1
                kl_sum += entry.get("kl_divergence", 0.0)

        results.append({
            "name": log_file.stem,
            "n_sampled": n,
            "top1_match_rate": round(n_match / n, 4) if n else None,
            "avg_kl_divergence": round(kl_sum / n, 6) if n else None,
        })
    return results


# ============================================================
# レポート生成
# ============================================================

def generate_html_report(
    accuracy: Dict[str, Any],
    model_versions: List[Dict],
    drift_reports: List[Dict],
    ab_summaries: List[Dict],
    shadow_stats: List[Dict],
    days: int,
) -> str:
    """HTML レポートを生成する"""
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    hit_rate_pct = accuracy["hit_rate"] * 100
    top3_pct = accuracy["top3_rate"] * 100

    # 日次的中率テーブル
    daily_rows = ""
    for date in sorted(accuracy["daily"].keys(), reverse=True)[:14]:
        d = accuracy["daily"][date]
        r = d["correct"] / d["total"] * 100 if d["total"] else 0
        daily_rows += f'<tr><td>{date}</td><td>{d["total"]}</td><td>{d["correct"]}</td><td>{r:.1f}%</td></tr>\n'

    # モデルバージョンテーブル
    model_rows = ""
    for v in model_versions[-5:]:
        prod_badge = ' <span class="badge">本番</span>' if v.get("is_production") else ""
        m = v.get("metrics", {})
        model_rows += (
            f'<tr><td>{v["version"]}{prod_badge}</td>'
            f'<td>{m.get("cv_logloss_mean", 0):.4f}</td>'
            f'<td>{m.get("cv_accuracy_mean", 0)*100:.1f}%</td>'
            f'<td>{m.get("n_samples", 0):,}</td>'
            f'<td>{v.get("registered_at", "")[:10]}</td></tr>\n'
        )

    # ドリフトテーブル
    drift_rows = ""
    for rpt in drift_reports[-5:]:
        status = "⚠️ 要再学習" if rpt.get("needs_retraining") else "✅ 安定"
        alerts = sum(
            1 for r in rpt.get("feature_results", []) if r.get("status") == "alert"
        )
        drift_rows += (
            f'<tr><td>{rpt.get("checked_at", "")[:16]}</td>'
            f'<td>{rpt.get("n_current", 0):,}</td>'
            f'<td>{alerts}</td><td>{status}</td></tr>\n'
        )

    # A/B テストテーブル
    ab_rows = ""
    for ab in ab_summaries:
        ab_rows += (
            f'<tr><td>{ab["name"]}</td><td>{ab["n_total"]}</td>'
            f'<td>{", ".join(ab["variants"].keys())}</td></tr>\n'
        )

    # シャドウ統計テーブル
    shadow_rows = ""
    for sh in shadow_stats:
        match = f'{sh["top1_match_rate"]*100:.1f}%' if sh["top1_match_rate"] else "N/A"
        kl = f'{sh["avg_kl_divergence"]:.6f}' if sh["avg_kl_divergence"] else "N/A"
        shadow_rows += (
            f'<tr><td>{sh["name"]}</td><td>{sh["n_sampled"]}</td>'
            f'<td>{match}</td><td>{kl}</td></tr>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>競艇予想AI パフォーマンスレポート</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; background: #f4f6f8; color: #333; }}
  .header {{ background: linear-gradient(135deg, #1a3a5c, #0d6efd); color: white; padding: 32px 40px; }}
  .header h1 {{ margin: 0; font-size: 1.8rem; }}
  .header p  {{ margin: 8px 0 0; opacity: .8; }}
  .container {{ max-width: 1100px; margin: 32px auto; padding: 0 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: white; border-radius: 10px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  .card .value {{ font-size: 2.2rem; font-weight: 700; color: #0d6efd; }}
  .card .label {{ font-size: .85rem; color: #888; margin-top: 4px; }}
  .section {{ background: white; border-radius: 10px; padding: 24px 28px; box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 24px; }}
  .section h2 {{ margin: 0 0 16px; font-size: 1.1rem; border-left: 4px solid #0d6efd; padding-left: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
  th {{ background: #f8f9fa; text-align: left; padding: 10px 12px; border-bottom: 2px solid #dee2e6; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f0f0f0; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ background: #198754; color: white; font-size: .7rem; padding: 2px 6px; border-radius: 4px; }}
  .footer {{ text-align: center; color: #aaa; font-size: .8rem; padding: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>競艇予想AI パフォーマンスレポート</h1>
  <p>生成日時: {now} ／ 集計期間: 直近 {days} 日間</p>
</div>
<div class="container">

  <!-- KPI カード -->
  <div class="cards">
    <div class="card">
      <div class="value">{hit_rate_pct:.1f}%</div>
      <div class="label">1着的中率</div>
    </div>
    <div class="card">
      <div class="value">{top3_pct:.1f}%</div>
      <div class="label">Top-3 的中率</div>
    </div>
    <div class="card">
      <div class="value">{accuracy["avg_prediction_rank"]:.2f}</div>
      <div class="label">平均予測順位</div>
    </div>
    <div class="card">
      <div class="value">{accuracy["n_results"]}</div>
      <div class="label">集計レース数</div>
    </div>
  </div>

  <!-- 日次的中率 -->
  <div class="section">
    <h2>日次的中率（直近14日）</h2>
    <table>
      <tr><th>日付</th><th>レース数</th><th>的中</th><th>的中率</th></tr>
      {daily_rows if daily_rows else '<tr><td colspan="4" style="text-align:center;color:#aaa">データなし</td></tr>'}
    </table>
  </div>

  <!-- モデルバージョン -->
  <div class="section">
    <h2>モデルバージョン（直近5件）</h2>
    <table>
      <tr><th>バージョン</th><th>CV LogLoss</th><th>CV Accuracy</th><th>学習サンプル数</th><th>登録日</th></tr>
      {model_rows if model_rows else '<tr><td colspan="5" style="text-align:center;color:#aaa">登録なし</td></tr>'}
    </table>
  </div>

  <!-- ドリフト検知 -->
  <div class="section">
    <h2>ドリフト検知履歴（直近5件）</h2>
    <table>
      <tr><th>チェック日時</th><th>サンプル数</th><th>アラート特徴量数</th><th>状態</th></tr>
      {drift_rows if drift_rows else '<tr><td colspan="4" style="text-align:center;color:#aaa">レポートなし</td></tr>'}
    </table>
  </div>

  <!-- A/Bテスト -->
  <div class="section">
    <h2>A/B テスト</h2>
    <table>
      <tr><th>テスト名</th><th>総レコード数</th><th>バリアント</th></tr>
      {ab_rows if ab_rows else '<tr><td colspan="3" style="text-align:center;color:#aaa">A/Bテストなし</td></tr>'}
    </table>
  </div>

  <!-- シャドウモード -->
  <div class="section">
    <h2>シャドウモード統計</h2>
    <table>
      <tr><th>名前</th><th>サンプル数</th><th>1位一致率</th><th>平均KL距離</th></tr>
      {shadow_rows if shadow_rows else '<tr><td colspan="4" style="text-align:center;color:#aaa">シャドウログなし</td></tr>'}
    </table>
  </div>

</div>
<div class="footer">競艇予想AI システム ／ 自動生成レポート</div>
</body>
</html>
"""


def generate_text_summary(accuracy: Dict[str, Any], model_versions: List[Dict], days: int) -> str:
    """テキスト形式のサマリーを生成する（Slack 通知用）"""
    lines = [
        f"📊 *競艇予想AI 週次レポート*（直近 {days} 日）",
        "",
        f"• 集計レース数: {accuracy['n_results']}",
        f"• 1着的中率: {accuracy['hit_rate']*100:.1f}%",
        f"• Top-3的中率: {accuracy['top3_rate']*100:.1f}%",
        f"• 平均予測順位: {accuracy['avg_prediction_rank']:.2f}",
    ]

    if model_versions:
        prod = next((v for v in model_versions if v.get("is_production")), None)
        if prod:
            m = prod.get("metrics", {})
            lines += [
                "",
                f"🤖 本番モデル: `{prod['version']}`",
                f"  CV LogLoss: {m.get('cv_logloss_mean', 0):.4f}",
                f"  学習サンプル: {m.get('n_samples', 0):,}",
            ]

    return "\n".join(lines)


# ============================================================
# メイン
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="週次パフォーマンスレポート生成")
    parser.add_argument("--days", type=int, default=7, help="集計期間（日数）")
    parser.add_argument("--out", type=str, default="output/report", help="出力ディレクトリ")
    parser.add_argument(
        "--format", choices=["html", "text", "both"], default="both", help="出力形式"
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # データ収集
    logger.info(f"レポートを生成しています（直近 {args.days} 日）...")

    from app.config import AB_LOG_DIR, DRIFT_REPORT_DIR, RESULT_LOG_DIR, SHADOW_LOG_DIR
    result_dir  = RESULT_LOG_DIR
    drift_dir   = DRIFT_REPORT_DIR
    ab_dir      = AB_LOG_DIR
    shadow_dir  = SHADOW_LOG_DIR

    accuracy      = collect_prediction_accuracy(result_dir if result_dir.exists() else Path(".nonexistent"), args.days)
    model_versions = collect_model_versions()
    drift_reports  = collect_drift_reports(drift_dir) if drift_dir.exists() else []
    ab_summaries   = collect_ab_test_summary(ab_dir) if ab_dir.exists() else []
    shadow_stats   = collect_shadow_stats(shadow_dir) if shadow_dir.exists() else []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.format in ("html", "both"):
        html = generate_html_report(
            accuracy, model_versions, drift_reports, ab_summaries, shadow_stats, args.days
        )
        html_path = out_dir / f"report_{timestamp}.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"HTML レポート: {html_path}")

    if args.format in ("text", "both"):
        text = generate_text_summary(accuracy, model_versions, args.days)
        text_path = out_dir / f"report_{timestamp}.txt"
        text_path.write_text(text, encoding="utf-8")
        print(f"\n" + text)
        print(f"\nテキストサマリー: {text_path}")

    logger.info("レポート生成完了")


if __name__ == "__main__":
    main()
