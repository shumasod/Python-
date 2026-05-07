"""
マルチアカウントコレクター テスト

AWS API コールはすべて unittest.mock でスタブ化する
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from rds_analyzer.collectors.multi_account_collector import (
    MultiAccountCollector,
    AccountCollectionResult,
    MultiAccountCollectionResult,
)
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType


def _make_instance(instance_id: str = "db-001", account_id: str = "111111111111") -> RDSInstance:
    return RDSInstance(
        instance_id=instance_id,
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
    )


class TestMultiAccountCollectionResult:

    def test_total_instances(self):
        r1 = AccountCollectionResult("111", "ap-northeast-1", instances=[_make_instance()])
        r2 = AccountCollectionResult("222", "ap-northeast-1", instances=[_make_instance(), _make_instance("db-002")])
        r3 = AccountCollectionResult("333", "ap-northeast-1", error="AccessDenied")
        result = MultiAccountCollectionResult(results=[r1, r2, r3])
        assert result.total_instances == 3

    def test_failed_accounts(self):
        r1 = AccountCollectionResult("111", "ap-northeast-1", instances=[])
        r2 = AccountCollectionResult("222", "us-east-1", error="AssumeRole failed")
        result = MultiAccountCollectionResult(results=[r1, r2])
        assert "222/us-east-1" in result.failed_accounts
        assert "111/ap-northeast-1" not in result.failed_accounts

    def test_all_instances_excludes_failed(self):
        inst = _make_instance()
        r1 = AccountCollectionResult("111", "ap-northeast-1", instances=[inst])
        r2 = AccountCollectionResult("222", "ap-northeast-1", error="timeout")
        result = MultiAccountCollectionResult(results=[r1, r2])
        all_inst = result.all_instances()
        assert len(all_inst) == 1
        assert all_inst[0].instance_id == inst.instance_id

    def test_success_property(self):
        ok = AccountCollectionResult("111", "ap-northeast-1")
        ng = AccountCollectionResult("222", "ap-northeast-1", error="oops")
        assert ok.success is True
        assert ng.success is False


class TestMultiAccountCollector:

    def _make_collector(self, accounts=None):
        accounts = accounts or ["111111111111", "222222222222"]
        collector = MultiAccountCollector(
            role_name="RDSAnalyzerReadOnly",
            accounts=accounts,
            regions=["ap-northeast-1"],
        )
        return collector

    @patch("rds_analyzer.collectors.multi_account_collector.boto3.client")
    def test_collect_all_returns_result(self, mock_boto_client):
        """collect_all が MultiAccountCollectionResult を返す"""
        collector = self._make_collector(accounts=["123456789012"])

        fake_sts = MagicMock()
        fake_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretAccessKey": "SECRET",
                "SessionToken": "TOKEN",
            }
        }
        mock_boto_client.return_value = fake_sts

        with patch(
            "rds_analyzer.collectors.multi_account_collector.CloudWatchCollector"
        ) as MockCW:
            mock_cw = MagicMock()
            mock_cw.list_rds_instances.return_value = [_make_instance()]
            mock_cw.collect_metrics_history.return_value = None
            MockCW.return_value = mock_cw

            result = collector.collect_all()

        assert isinstance(result, MultiAccountCollectionResult)
        assert len(result.results) == 1

    @patch("rds_analyzer.collectors.multi_account_collector.boto3.client")
    def test_assume_role_failure_is_partial(self, mock_boto_client):
        """1アカウントの AssumeRole 失敗が全体を止めない"""
        from botocore.exceptions import ClientError

        collector = self._make_collector(accounts=["111111111111", "222222222222"])

        fake_sts = MagicMock()
        fake_sts.assume_role.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "AssumeRole"
        )
        mock_boto_client.return_value = fake_sts

        result = collector.collect_all()

        assert len(result.results) == 2
        assert all(not r.success for r in result.results)
        assert len(result.failed_accounts) == 2

    def test_default_region_is_ap_northeast_1(self):
        collector = MultiAccountCollector(
            role_name="MyRole",
            accounts=["123456789012"],
        )
        assert collector.regions == ["ap-northeast-1"]

    def test_multiple_regions_creates_multiple_tasks(self):
        """2 アカウント × 2 リージョン = 4 タスク"""
        collector = MultiAccountCollector(
            role_name="MyRole",
            accounts=["111111111111", "222222222222"],
            regions=["ap-northeast-1", "us-east-1"],
        )
        tasks = [
            (a, r)
            for a in collector.accounts
            for r in collector.regions
        ]
        assert len(tasks) == 4
