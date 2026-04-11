"""
競艇データパイプライン Airflow DAG

スケジュール: 毎日 06:00 JST（レース開始前に前日データを収集）

パイプライン構成:
  1. scrape_results    : 前日のレース結果を収集
  2. scrape_racers     : 選手情報を更新（週1回のみ実行）
  3. validate_data     : 収集データの品質チェック
  4. retrain_model     : 新データでモデルを再学習（月曜のみ）
  5. notify_complete   : Slack 通知（任意）

実行方法（ローカル Airflow）:
  airflow dags trigger boat_race_pipeline
  airflow dags backfill --start-date 2024-01-01 --end-date 2024-01-31 boat_race_pipeline
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---- デフォルト引数 ----
default_args = {
    "owner": "boat-race-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


# ============================================================
# タスク関数
# ============================================================

def task_scrape_results(**context) -> dict:
    """前日のレース結果を収集する"""
    from scraper import scrape_race_results
    from datetime import date, timedelta

    # Airflow の execution_date から対象日を取得
    execution_date = context["data_interval_start"].date()
    target_date = execution_date - timedelta(days=1)

    records = scrape_race_results(
        start_date=target_date,
        end_date=target_date,
    )

    # 次タスクに件数を渡す（XCom）
    return {"scraped_count": len(records), "target_date": str(target_date)}


def task_should_scrape_racers(**context) -> bool:
    """
    週1回（月曜日）だけ選手情報スクレイピングを実行する
    ShortCircuitOperator 用の条件関数
    """
    execution_date = context["data_interval_start"]
    return execution_date.weekday() == 0  # 0 = 月曜日


def task_scrape_racers(**context) -> dict:
    """選手情報を更新する"""
    from scraper import scrape_racer_info

    records = scrape_racer_info()
    return {"racer_count": len(records)}


def task_validate_data(**context) -> None:
    """
    収集データの品質チェック
    - 件数が 0 の場合は警告
    - 必須カラムの欠損チェック
    """
    import logging
    logger = logging.getLogger(__name__)

    ti = context["ti"]
    result = ti.xcom_pull(task_ids="scrape_results")
    scraped_count = result.get("scraped_count", 0) if result else 0

    if scraped_count == 0:
        logger.warning("スクレイピング結果が 0 件です。サイト構造が変わった可能性があります。")
        # 0件でもパイプラインは継続（アラートのみ）
    else:
        logger.info(f"データ品質チェック OK: {scraped_count} 件")


def task_should_retrain(**context) -> bool:
    """
    週1回（月曜日）だけ再学習を実行する
    """
    execution_date = context["data_interval_start"]
    return execution_date.weekday() == 0


def task_retrain_model(**context) -> dict:
    """
    蓄積データでモデルを再学習する
    モデルファイルは models/ ディレクトリに上書き保存
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from app.data.loader import load_training_data
        from app.model.train import train_model

        logger.info("モデル再学習を開始します")

        # 実データがあれば使用、なければサンプルで代替
        try:
            df = load_training_data()
        except FileNotFoundError:
            logger.warning("実データなし。サンプルデータで学習します。")
            df = load_training_data(use_sample=True)

        _, metrics = train_model(df, model_name="boat_race_model")

        logger.info(f"再学習完了: logloss={metrics['cv_logloss_mean']:.4f}")
        return {"status": "retrained", "metrics": metrics}

    except Exception as e:
        logger.error(f"再学習エラー: {e}")
        raise


def task_check_drift(**context) -> dict:
    """
    ドリフト検知: 最新データと参照分布を比較し、
    PSI が高い特徴量があれば警告をログに記録する
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from app.model.drift import DriftDetector
        from app.model.features import generate_sample_training_data, preprocess_dataframe

        detector = DriftDetector()

        # 参照分布が未設定の場合はサンプルデータで初期化
        if not detector._reference_stats:
            logger.warning("参照分布が未設定。サンプルデータで初期化します。")
            ref_df = preprocess_dataframe(generate_sample_training_data(n_races=500))
            detector.set_reference(ref_df)

        # 直近データでドリフトチェック（実運用では当日データを使用）
        current_df = preprocess_dataframe(generate_sample_training_data(n_races=100))
        report = detector.check(current_df)

        alert_features = [r.feature for r in report.feature_results if r.status == "alert"]
        warn_features  = [r.feature for r in report.feature_results if r.status == "warn"]

        if alert_features:
            logger.error(f"ドリフトアラート! 要再学習: {alert_features}")
        elif warn_features:
            logger.warning(f"ドリフト警告: {warn_features}")
        else:
            logger.info("ドリフト検知: 全特徴量が安定しています")

        return {
            "needs_retraining": report.needs_retraining,
            "alert_features": alert_features,
            "warn_features": warn_features,
        }

    except Exception as e:
        logger.error(f"ドリフト検知エラー: {e}")
        return {"needs_retraining": False, "error": str(e)}


def task_notify(**context) -> None:
    """
    パイプライン完了通知
    Slack Webhook URL を Airflow Connection に設定すれば実際に送信可能
    """
    import logging
    logger = logging.getLogger(__name__)

    ti = context["ti"]
    scrape_result = ti.xcom_pull(task_ids="scrape_results") or {}
    retrain_result = ti.xcom_pull(task_ids="retrain_model") or {}

    msg = (
        f"[競艇AI] パイプライン完了\n"
        f"収集件数: {scrape_result.get('scraped_count', 'N/A')}\n"
        f"再学習: {retrain_result.get('status', 'スキップ')}\n"
        f"実行日時: {context['data_interval_start']}"
    )
    logger.info(msg)

    # Slack 通知の実装例（SlackWebhookOperator を使う場合はコメントを解除）
    # from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
    # SlackWebhookOperator(
    #     task_id="slack_notify",
    #     http_conn_id="slack_webhook",
    #     message=msg,
    # ).execute(context)


# ============================================================
# DAG 定義
# ============================================================

with DAG(
    dag_id="boat_race_pipeline",
    default_args=default_args,
    description="競艇データ収集・モデル再学習パイプライン",
    schedule_interval="0 21 * * *",  # UTC 21:00 = JST 06:00
    start_date=days_ago(1),
    catchup=False,  # 過去分は実行しない（バックフィル時は True に変更）
    max_active_runs=1,  # 同時実行は1パイプラインのみ
    tags=["boat-race", "ml", "scraping"],
) as dag:

    start = EmptyOperator(task_id="start")

    # レース結果収集
    scrape_results = PythonOperator(
        task_id="scrape_results",
        python_callable=task_scrape_results,
    )

    # データ品質チェック
    validate = PythonOperator(
        task_id="validate_data",
        python_callable=task_validate_data,
    )

    # 選手情報収集（週1回のみ）
    check_racer_scrape = ShortCircuitOperator(
        task_id="check_racer_scrape",
        python_callable=task_should_scrape_racers,
    )

    scrape_racers = PythonOperator(
        task_id="scrape_racers",
        python_callable=task_scrape_racers,
    )

    # ドリフト検知（毎日実行）
    drift_check = PythonOperator(
        task_id="drift_check",
        python_callable=task_check_drift,
    )

    # モデル再学習（週1回のみ）
    check_retrain = ShortCircuitOperator(
        task_id="check_retrain",
        python_callable=task_should_retrain,
    )

    retrain_model = PythonOperator(
        task_id="retrain_model",
        python_callable=task_retrain_model,
    )

    # 完了通知
    notify = PythonOperator(
        task_id="notify",
        python_callable=task_notify,
        trigger_rule="all_done",  # 上流が失敗しても通知は実行
    )

    end = EmptyOperator(task_id="end")

    # ---- タスク依存関係 ----
    # start → scrape_results → validate → drift_check → notify → end
    #                        ↘ check_racer_scrape → scrape_racers ↗
    #                        ↘ check_retrain → retrain_model      ↗

    start >> scrape_results >> validate
    validate >> [check_racer_scrape, check_retrain, drift_check]
    check_racer_scrape >> scrape_racers >> notify
    check_retrain >> retrain_model >> notify
    drift_check >> notify
    notify >> end
