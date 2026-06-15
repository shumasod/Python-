"""
マルチアカウント RDS メトリクス収集

設計意図:
- AWS Organizations / AssumeRole を使って複数アカウントを一括収集
- 各アカウントの CloudWatch/RDS データを並行取得してレイテンシを最小化
- アカウントごとに失敗しても他アカウントへの影響を最小化（partial failure 許容）

使用方法:
    collector = MultiAccountCollector(
        role_name="RDSAnalyzerReadOnly",
        accounts=["123456789012", "234567890123"],
        regions=["ap-northeast-1", "us-east-1"],
    )
    results = collector.collect_all()
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from rds_analyzer.collectors.cloudwatch_collector import CloudWatchCollector
from rds_analyzer.models.metrics import MetricsHistory
from rds_analyzer.models.rds import RDSInstance

logger = logging.getLogger(__name__)


@dataclass
class AccountCollectionResult:
    """1アカウント × 1リージョンの収集結果"""
    account_id: str
    region: str
    instances: list[RDSInstance] = field(default_factory=list)
    metrics: list[MetricsHistory] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class MultiAccountCollectionResult:
    """全アカウントの収集サマリー"""
    results: list[AccountCollectionResult]
    collected_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def total_instances(self) -> int:
        return sum(len(r.instances) for r in self.results if r.success)

    @property
    def failed_accounts(self) -> list[str]:
        return [f"{r.account_id}/{r.region}" for r in self.results if not r.success]

    def all_metrics(self) -> list[MetricsHistory]:
        return [m for r in self.results if r.success for m in r.metrics]

    def all_instances(self) -> list[RDSInstance]:
        return [i for r in self.results if r.success for i in r.instances]


class MultiAccountCollector:
    """
    AWS Organizations の複数アカウントから RDS メトリクスを並行収集する

    AssumeRole を使用して各アカウントに一時的な認証情報を取得する。
    IAM ロール名は全アカウントで統一する必要がある。
    """

    # IAM AssumeRole の有効期間（秒）
    SESSION_DURATION_SECONDS = 3600

    def __init__(
        self,
        role_name: str,
        accounts: list[str],
        regions: list[str] | None = None,
        collection_period_hours: int = 24,
        max_workers: int = 10,
        external_id: str | None = None,
    ):
        """
        Args:
            role_name: 各アカウントで AssumeRole するロール名
            accounts: AWS アカウント ID のリスト
            regions: 収集対象リージョン（None の場合は ap-northeast-1 のみ）
            collection_period_hours: CloudWatch 取得期間（時間）
            max_workers: 並行スレッド数（アカウント数 × リージョン数 を超えないように設定）
            external_id: AssumeRole の ExternalId（セキュリティ強化用）
        """
        self.role_name = role_name
        self.accounts = accounts
        self.regions = regions or ["ap-northeast-1"]
        self.collection_period_hours = collection_period_hours
        self.max_workers = max_workers
        self.external_id = external_id

        self._sts_client = boto3.client("sts")

    def collect_all(self) -> MultiAccountCollectionResult:
        """
        全アカウント × 全リージョンのメトリクスを並行収集する

        Returns:
            MultiAccountCollectionResult (partial failure を含む場合あり)
        """
        tasks = [
            (account_id, region)
            for account_id in self.accounts
            for region in self.regions
        ]

        results: list[AccountCollectionResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._collect_account_region, account_id, region): (account_id, region)
                for account_id, region in tasks
            }

            for future in as_completed(future_to_task):
                account_id, region = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.error(
                        "Unexpected error collecting %s/%s: %s",
                        account_id, region, exc
                    )
                    results.append(AccountCollectionResult(
                        account_id=account_id,
                        region=region,
                        error=str(exc),
                    ))

        summary = MultiAccountCollectionResult(results=results)
        if summary.failed_accounts:
            logger.warning(
                "Collection failed for %d account/regions: %s",
                len(summary.failed_accounts),
                summary.failed_accounts,
            )

        logger.info(
            "Multi-account collection complete: %d instances across %d account/regions",
            summary.total_instances,
            len([r for r in results if r.success]),
        )
        return summary

    def _collect_account_region(
        self, account_id: str, region: str
    ) -> AccountCollectionResult:
        """1アカウント × 1リージョンの収集処理"""
        try:
            session = self._assume_role(account_id, region)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.warning(
                "AssumeRole failed for %s/%s: %s", account_id, region, error_code
            )
            return AccountCollectionResult(
                account_id=account_id,
                region=region,
                error=f"AssumeRole failed: {error_code}",
            )

        try:
            collector = CloudWatchCollector(
                session=session,
                region=region,
                period_hours=self.collection_period_hours,
            )
            instances = collector.list_rds_instances()
            metrics: list[MetricsHistory] = []

            for instance in instances:
                try:
                    m = collector.collect_metrics_history(instance.instance_id)
                    if m:
                        metrics.append(m)
                except Exception as exc:
                    logger.warning(
                        "Failed to collect metrics for %s in %s/%s: %s",
                        instance.instance_id, account_id, region, exc,
                    )

            return AccountCollectionResult(
                account_id=account_id,
                region=region,
                instances=instances,
                metrics=metrics,
            )

        except Exception as exc:
            logger.error(
                "Collection error for %s/%s: %s", account_id, region, exc
            )
            return AccountCollectionResult(
                account_id=account_id,
                region=region,
                error=str(exc),
            )

    def _assume_role(self, account_id: str, region: str) -> boto3.Session:
        """AssumeRole して boto3 Session を返す"""
        role_arn = f"arn:aws:iam::{account_id}:role/{self.role_name}"
        session_name = f"RDSAnalyzer-{account_id}-{region}"

        assume_kwargs: dict = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": self.SESSION_DURATION_SECONDS,
        }
        if self.external_id:
            assume_kwargs["ExternalId"] = self.external_id

        response = self._sts_client.assume_role(**assume_kwargs)
        creds = response["Credentials"]

        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        )

    def list_accounts_from_organizations(self) -> list[str]:
        """
        AWS Organizations から管理下のアカウント一覧を取得する

        管理アカウント（payer account）から実行する必要がある。
        Organizations の ListAccounts 権限が必要。

        Returns:
            アクティブなアカウント ID のリスト
        """
        org_client = boto3.client("organizations")
        account_ids: list[str] = []

        paginator = org_client.get_paginator("list_accounts")
        for page in paginator.paginate():
            for account in page["Accounts"]:
                if account["Status"] == "ACTIVE":
                    account_ids.append(account["Id"])

        logger.info("Found %d active accounts in Organizations", len(account_ids))
        return account_ids
