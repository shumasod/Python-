#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
改良版: GCP Monitor for App Engine + GCS logging
- 設定は環境変数 or CLI
- gcloud 呼び出しのエラーハンドリング強化 (timeout, stderr)
- GCS 操作に単純な再試行と詳細ログを追加
- 古いログ削除のロジック修正（timedelta、time_created ガード）
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Callable, Any

from google.cloud import storage
from google.api_core import exceptions as api_exceptions

# ロギング設定（実行環境で設定されていればそちらに任せても良い）
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("gcp_monitor")


class GCPError(Exception):
    """GCP 操作関連のカスタム例外"""
    pass


def retry(func: Callable[..., Any], retries: int = 3, backoff: float = 1.0, exceptions=(Exception,)):
    """
    シンプルな retry ヘルパー（指数バックオフ）
    """
    def wrapper(*args, **kwargs):
        attempt = 0
        while True:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                attempt += 1
                if attempt > retries:
                    logger.debug("リトライ上限到達", exc_info=True)
                    raise
                sleep = backoff * (2 ** (attempt - 1))
                logger.warning(f"Retry {attempt}/{retries} after exception: {e}. Sleeping {sleep}s")
                time.sleep(sleep)
    return wrapper


@dataclass
class Config:
    project_id: str
    service_name: str
    version: str
    bucket_name: str
    gcloud_timeout: int = 15  # seconds
    cleanup_days: int = 90
    retry_attempts: int = 3
    retry_backoff: float = 1.0


class GCPMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.storage_client = storage.Client(project=cfg.project_id)
        logger.debug(f"Initialized storage client for project {cfg.project_id}")

    def _run_gcloud(self, args: list[str], timeout: Optional[int] = None) -> str:
        """gcloud を呼んで stdout を返す。失敗時は詳細ログを含む例外を出す。"""
        timeout = timeout or self.cfg.gcloud_timeout
        cmd = ["gcloud"] + args + ["--project", self.cfg.project_id, "--format", "json"]
        logger.debug(f"Running command: {' '.join(cmd)} (timeout={timeout}s)")
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            logger.debug("gcloud stdout: %s", completed.stdout[:1000])  # 過度な出力を避ける
            return completed.stdout
        except subprocess.CalledProcessError as e:
            msg = f"gcloud returned non-zero exit status {e.returncode}. stderr: {e.stderr.strip()}"
            logger.error(msg)
            raise GCPError(msg)
        except subprocess.TimeoutExpired as e:
            msg = f"gcloud timed out after {timeout}s. stdout: {e.stdout}, stderr: {e.stderr}"
            logger.error(msg)
            raise GCPError(msg)
        except FileNotFoundError:
            msg = "gcloud CLI が見つかりません。実行環境に Cloud SDK がインストールされているか確認してください。"
            logger.error(msg)
            raise GCPError(msg)

    def get_app_engine_endpoint(self) -> Optional[str]:
        """
        App Engine サービスのバージョンから endpoint を探す。
        - gcloud app services describe <service> --format json
        """
        try:
            out = self._run_gcloud(["app", "services", "describe", self.cfg.service_name])
            service_info = json.loads(out)
        except json.JSONDecodeError as e:
            raise GCPError(f"gcloud の出力が JSON として解釈できません: {e}")
        except GCPError:
            raise

        versions = service_info.get("versions") or []
        if not isinstance(versions, list):
            logger.warning("サービス情報の 'versions' がリストではありません。内容をログに出します。")
            logger.debug("service_info: %s", service_info)
            return None

        for v in versions:
            if v.get("id") == self.cfg.version:
                url = v.get("versionUrl") or v.get("url") or v.get("version_url")
                if url:
                    return url
                # 万一構造が異なる場合は追加チェック
                logger.debug("見つかったバージョンオブジェクト: %s", v)
        logger.warning("指定バージョンが見つかりません: %s", self.cfg.version)
        return None

    @retry
    def save_log(self, log_data: str) -> str:
        """
        ログを Cloud Storage に保存。成功したらオブジェクト名を返す。
        再試行はデコレータ retry で行う（主に transient error 対応）。
        """
        try:
            bucket = self.storage_client.bucket(self.cfg.bucket_name)
            # ここでは bucket.exists() を呼ばない（API 互換の違い回避）代わりに upload 時に起きる例外をキャッチする
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            filename = f"log_{timestamp}.txt"
            blob = bucket.blob(filename)
            blob.upload_from_string(log_data)
            # サイズ等をログ出力（読み取りは数秒遅延することがある）
            logger.info(f"ログを保存しました: gs://{self.cfg.bucket_name}/{filename}")
            try:
                # blob.reload() をするとメタ情報が来る（存在確認）
                blob.reload()
                logger.info(f"Saved object size={blob.size} bytes, content_type={blob.content_type}")
            except Exception:
                logger.debug("blob metadata の取得に失敗しました（読み取り可能性の遅延の可能性）", exc_info=True)
            return filename
        except api_exceptions.GoogleAPICallError as e:
            # API 呼び出し系の共通エラー: NotFound / Forbidden 等を含む
            msg = f"GCS API error while saving log: {e}"
            logger.error(msg, exc_info=True)
            raise GCPError(msg)
        except Exception as e:
            msg = f"Unexpected error while saving log: {e}"
            logger.exception(msg)
            raise GCPError(msg)

    @retry
    def cleanup_old_logs(self, days: int | None = None) -> None:
        """
        指定日数より古いログを削除する。
        - days None の場合は cfg.cleanup_days を使う
        - blob.time_created が None の場合はスキップしてログを残す
        """
        days = days if days is not None else self.cfg.cleanup_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(f"Cleaning up objects older than {cutoff.isoformat()} (UTC)")
        try:
            bucket = self.storage_client.bucket(self.cfg.bucket_name)
            # list_blobs は遅延評価。大量オブジェクトがある場合は prefix の検討を。
            deleted_count = 0
            for blob in bucket.list_blobs():
                created = getattr(blob, "time_created", None)
                if created is None:
                    logger.debug(f"オブジェクト {blob.name} に作成時間が無いためスキップ")
                    continue
                if created < cutoff:
                    try:
                        blob.delete()
                        deleted_count += 1
                        logger.info(f"Deleted old log: {blob.name} (created: {created.isoformat()})")
                    except api_exceptions.GoogleAPICallError as e:
                        logger.warning(f"Failed to delete {blob.name}: {e}")
            logger.info(f"Old logs cleanup finished. deleted_count={deleted_count}")
        except api_exceptions.GoogleAPICallError as e:
            msg = f"GCS API error during cleanup: {e}"
            logger.error(msg, exc_info=True)
            raise GCPError(msg)
        except Exception as e:
            logger.exception("Unexpected error during cleanup")
            raise GCPError(str(e))


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Monitor App Engine and save logs to GCS")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID"), help="GCP Project ID")
    parser.add_argument("--service-name", default=os.environ.get("APP_ENGINE_SERVICE"), help="App Engine service name")
    parser.add_argument("--version", default=os.environ.get("APP_ENGINE_VERSION"), help="App Engine version id")
    parser.add_argument("--bucket", "--bucket-name", default=os.environ.get("GCS_BUCKET"), help="GCS bucket name")
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("GCLOUD_TIMEOUT", "15")), help="gcloud timeout seconds")
    parser.add_argument("--cleanup-days", type=int, default=int(os.environ.get("CLEANUP_DAYS", "90")), help="days to keep logs")
    args = parser.parse_args()

    required = {
        "project_id": args.project_id,
        "service_name": args.service_name,
        "version": args.version,
        "bucket_name": args.bucket
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.error("必須パラメータが見つかりません: %s. 環境変数で指定することもできます (GCP_PROJECT_ID, APP_ENGINE_SERVICE, APP_ENGINE_VERSION, GCS_BUCKET)", missing)
        sys.exit(2)

    return Config(
        project_id=args.project_id,
        service_name=args.service_name,
        version=args.version,
        bucket_name=args.bucket,
        gcloud_timeout=args.timeout,
        cleanup_days=args.cleanup_days,
        retry_attempts=3,
        retry_backoff=1.0
    )


def main() -> None:
    cfg = parse_args()
    monitor = GCPMonitor(cfg)
    try:
        endpoint = monitor.get_app_engine_endpoint()
        if not endpoint:
            logger.error("エンドポイントが取得できませんでした（バージョンが見つからない可能性）")
            sys.exit(1)
        logger.info(f"App Engine endpoint: {endpoint}")
        log_data = f"[{datetime.now(timezone.utc).isoformat()}] Monitoring App Engine Endpoint: {endpoint}\n"
        saved = monitor.save_log(log_data)
        logger.info(f"Saved log object: {saved}")
        monitor.cleanup_old_logs()
    except GCPError as e:
        logger.error("GCP 操作でエラー: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("予期しないエラー")
        sys.exit(1)


if __name__ == "__main__":
    main()
