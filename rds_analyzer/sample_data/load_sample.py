"""
サンプルデータローダー

設計意図:
- 開発・デモ環境向けに sample_instances.json のデータを API に投入するスクリプト
- uvicorn 起動中の FastAPI エンドポイントに直接リクエストを送る
- 全サンプルシナリオを一括登録することで即座にダッシュボードを確認可能

使用方法:
    # バックエンド起動後に実行
    python -m rds_analyzer.sample_data.load_sample

    # ベース URL を指定する場合
    RDS_API_URL=http://localhost:8000 python -m rds_analyzer.sample_data.load_sample
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import urllib.request
import urllib.error

BASE_URL = os.environ.get("RDS_API_URL", "http://localhost:8000")
SAMPLE_FILE = Path(__file__).parent / "sample_instances.json"


def _post(path: str, payload: dict) -> dict:
    """シンプルな HTTP POST ヘルパー"""
    url = f"{BASE_URL}/api/v1{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  ✗ HTTP {e.code}: {body[:200]}")
        return {}
    except urllib.error.URLError as e:
        print(f"  ✗ 接続エラー: {e.reason}")
        print(f"    バックエンドが起動しているか確認: {BASE_URL}")
        sys.exit(1)


def load_sample_data() -> None:
    """サンプルデータを API に投入する"""
    print(f"📊 サンプルデータ投入先: {BASE_URL}")
    print("=" * 60)

    with open(SAMPLE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for item in data["instances"]:
        scenario = item["scenario"]
        instance = item["instance"]
        metrics = item["metrics"]
        instance_id = instance["instance_id"]

        print(f"\n[{scenario}]")
        print(f"  インスタンスID: {instance_id}")

        # 1. インスタンス登録
        result = _post("/rds", instance)
        if result:
            print(f"  ✓ インスタンス登録完了")

        # 2. メトリクス投入
        metrics_payload = {"instance_id": instance_id, "period_hours": 24, **metrics}
        result = _post(f"/rds/{instance_id}/metrics", metrics_payload)
        if result:
            print(f"  ✓ メトリクス投入完了")

    print("\n" + "=" * 60)
    print(f"✅ 完了！ ダッシュボードを確認: {BASE_URL}/docs")
    print(f"   全インスタンス概要: GET {BASE_URL}/api/v1/rds/summary")


if __name__ == "__main__":
    load_sample_data()
