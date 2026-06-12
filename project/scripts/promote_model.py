"""
モデル昇格スクリプト
指定バージョンを本番モデルとして昇格する（ロールバック用途にも使用可）

実行例:
  # 最新バージョンを本番へ昇格
  python scripts/promote_model.py --latest

  # 特定バージョンを本番へ昇格（ロールバック）
  python scripts/promote_model.py --version boat_race_model_v20240401_1

  # バージョン一覧を表示
  python scripts/promote_model.py --list

  # 古いバージョンを削除（最新10件を保持）
  python scripts/promote_model.py --cleanup --keep 10
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.versioning import ModelRegistry
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="競艇AIモデル昇格・バージョン管理")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--version", type=str, help="昇格するバージョン文字列")
    group.add_argument("--latest", action="store_true", help="最新バージョンを昇格")
    group.add_argument("--list", action="store_true", help="バージョン一覧を表示")
    group.add_argument("--cleanup", action="store_true", help="古いバージョンを削除")
    parser.add_argument("--keep", type=int, default=10, help="--cleanup 時に保持するバージョン数")
    args = parser.parse_args()

    registry = ModelRegistry()

    if args.list:
        registry.print_summary()
        return

    if args.cleanup:
        deleted = registry.cleanup_old_versions(keep=args.keep)
        print(f"{deleted} ファイルを削除しました")
        return

    # 昇格対象バージョンを決定
    if args.latest:
        versions = registry.list_versions()
        if not versions:
            print("登録済みバージョンがありません。先にモデルを学習してください。")
            sys.exit(1)
        target_version = versions[-1]["version"]
        print(f"最新バージョンを昇格します: {target_version}")
    else:
        target_version = args.version

    # 確認プロンプト
    current = registry.get_production_version()
    print(f"\n現在の本番バージョン: {current or 'なし'}")
    print(f"昇格するバージョン  : {target_version}")
    confirm = input("\n本番モデルを更新しますか？ [y/N]: ").strip().lower()

    if confirm != "y":
        print("昇格をキャンセルしました")
        return

    try:
        registry.promote(target_version)
        print(f"\n本番モデルを更新しました: {target_version}")
        registry.print_summary()
    except FileNotFoundError as e:
        print(f"エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
