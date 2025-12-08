#!/usr/bin/env python3
"""
Excelファイル結合ツール

複数のExcelファイルを効率的に結合するCLIツール。
列互換性チェック、重複削除、ソート、メタデータ出力に対応。

Usage:
    python excel_merger.py -d ./data -o merged.xlsx
    python excel_merger.py file1.xlsx file2.xlsx -o output.xlsx --add-source
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from dataclasses import dataclass, field
from enum import Enum, auto
from glob import glob
from pathlib import Path
from typing import Any

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# =============================================================================
# Types & Configuration
# =============================================================================


class OutputFormat(Enum):
    """出力フォーマット"""

    XLSX = auto()
    CSV = auto()

    @classmethod
    def from_path(cls, path: Path) -> OutputFormat:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return cls.CSV
        return cls.XLSX


@dataclass
class MergeConfig:
    """結合設定"""

    output_path: Path
    sheet_name: str | None = None
    add_source_column: bool = False
    sort_by: str | None = None
    remove_duplicates: bool = False
    validate_columns: bool = True
    add_metadata_sheet: bool = True


@dataclass
class MergeStats:
    """結合統計"""

    total_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    total_rows: int = 0
    final_rows: int = 0
    duplicates_removed: int = 0

    def summary(self) -> str:
        return (
            f"対象ファイル: {self.total_files}\n"
            f"成功: {self.successful_files}\n"
            f"失敗: {self.failed_files}\n"
            f"総行数: {self.total_rows:,}\n"
            f"重複削除: {self.duplicates_removed:,}\n"
            f"最終行数: {self.final_rows:,}"
        )


@dataclass
class FileInfo:
    """ファイル情報"""

    path: Path
    status: str = "pending"
    rows: int = 0
    error: str | None = None


# =============================================================================
# Logging
# =============================================================================


def setup_logging(verbose: bool = False, log_file: Path | None = None) -> logging.Logger:
    """ロガーをセットアップ"""
    logger = logging.getLogger("excel_merger")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# =============================================================================
# File Discovery
# =============================================================================


EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}


def is_excel_file(path: Path) -> bool:
    """Excelファイルかどうかを判定"""
    return path.suffix.lower() in EXCEL_EXTENSIONS


def discover_excel_files(
    patterns: list[str],
    recursive: bool = False,
) -> list[Path]:
    """Excelファイルを検出"""
    files: set[Path] = set()

    for pattern in patterns:
        path = Path(pattern)

        if path.is_file() and is_excel_file(path):
            files.add(path.resolve())

        elif path.is_dir():
            glob_pattern = "**/*.xls*" if recursive else "*.xls*"
            for match in path.glob(glob_pattern):
                if match.is_file() and is_excel_file(match):
                    files.add(match.resolve())

        else:
            # globパターンとして処理
            for match in glob(pattern, recursive=recursive):
                match_path = Path(match)
                if match_path.is_file() and is_excel_file(match_path):
                    files.add(match_path.resolve())

    return sorted(files)


# =============================================================================
# Validation
# =============================================================================


class ColumnValidator:
    """列互換性検証"""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def validate(
        self,
        files: list[Path],
        sheet_name: str | None = None,
    ) -> tuple[bool, list[str]]:
        """ファイル間の列互換性をチェック"""
        if len(files) < 2:
            return True, []

        reference_columns: list[str] | None = None
        reference_file: Path | None = None
        issues: list[str] = []

        for file_path in files:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
                columns = list(df.columns)

                if reference_columns is None:
                    reference_columns = columns
                    reference_file = file_path
                elif columns != reference_columns:
                    issue = (
                        f"列が異なります:\n"
                        f"  基準: {reference_file.name} → {reference_columns}\n"
                        f"  対象: {file_path.name} → {columns}"
                    )
                    issues.append(issue)
                    self._logger.warning(issue)

            except Exception as e:
                self._logger.error("検証エラー (%s): %s", file_path.name, e)
                issues.append(f"{file_path.name}: {e}")

        return len(issues) == 0, issues


# =============================================================================
# Excel Merger
# =============================================================================


class ExcelMerger:
    """Excel結合処理"""

    def __init__(
        self,
        config: MergeConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("excel_merger")
        self._validator = ColumnValidator(self._logger)
        self._file_infos: list[FileInfo] = []

    def merge(self, files: list[Path]) -> MergeStats:
        """Excelファイルを結合"""
        if not files:
            raise ValueError("結合するファイルがありません")

        # ファイル存在確認
        missing = [f for f in files if not f.exists()]
        if missing:
            raise FileNotFoundError(f"ファイルが見つかりません: {missing}")

        # 出力ディレクトリ作成
        self._config.output_path.parent.mkdir(parents=True, exist_ok=True)

        # 列互換性チェック
        if self._config.validate_columns:
            is_valid, issues = self._validator.validate(files, self._config.sheet_name)
            if not is_valid:
                self._logger.warning("列の構造が異なるファイルがあります")

        # ファイル読み込み
        stats = MergeStats(total_files=len(files))
        self._file_infos = [FileInfo(path=f) for f in files]
        dataframes: list[pd.DataFrame] = []

        for i, file_info in enumerate(self._file_infos, 1):
            self._logger.info(
                "読み込み中 [%d/%d]: %s",
                i,
                len(files),
                file_info.path.name,
            )

            try:
                df = self._read_file(file_info.path)

                if df.empty:
                    self._logger.warning("空のファイルをスキップ: %s", file_info.path.name)
                    file_info.status = "skipped"
                    continue

                if self._config.add_source_column:
                    df["source_file"] = file_info.path.name

                dataframes.append(df)
                file_info.status = "success"
                file_info.rows = len(df)
                stats.successful_files += 1
                stats.total_rows += len(df)

            except Exception as e:
                self._logger.error("読み込みエラー (%s): %s", file_info.path.name, e)
                file_info.status = "failed"
                file_info.error = str(e)
                stats.failed_files += 1

        if not dataframes:
            raise ValueError("読み込み可能なファイルがありませんでした")

        # 結合
        self._logger.info("データを結合中...")
        merged_df = pd.concat(dataframes, ignore_index=True, sort=False)

        # 重複削除
        if self._config.remove_duplicates:
            before = len(merged_df)
            merged_df = merged_df.drop_duplicates()
            stats.duplicates_removed = before - len(merged_df)
            self._logger.info("重複削除: %d行", stats.duplicates_removed)

        # ソート
        if self._config.sort_by:
            if self._config.sort_by in merged_df.columns:
                merged_df = merged_df.sort_values(by=self._config.sort_by)
                self._logger.info("ソート完了: %s", self._config.sort_by)
            else:
                self._logger.warning("ソート列が見つかりません: %s", self._config.sort_by)

        stats.final_rows = len(merged_df)

        # 出力
        self._write_output(merged_df)

        return stats

    def _read_file(self, path: Path) -> pd.DataFrame:
        """Excelファイルを読み込み"""
        return pd.read_excel(path, sheet_name=self._config.sheet_name)

    def _write_output(self, df: pd.DataFrame) -> None:
        """結果を出力"""
        output_format = OutputFormat.from_path(self._config.output_path)

        self._logger.info("ファイル出力中: %s", self._config.output_path)

        if output_format == OutputFormat.CSV:
            df.to_csv(self._config.output_path, index=False, encoding="utf-8-sig")
        else:
            with pd.ExcelWriter(self._config.output_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="MergedData", index=False)

                if self._config.add_metadata_sheet:
                    self._write_metadata_sheet(writer)

    def _write_metadata_sheet(self, writer: pd.ExcelWriter) -> None:
        """メタデータシートを追加"""
        metadata = pd.DataFrame([
            {
                "ファイル名": info.path.name,
                "パス": str(info.path),
                "状態": info.status,
                "行数": info.rows if info.status == "success" else 0,
                "エラー": info.error or "",
            }
            for info in self._file_infos
        ])
        metadata.to_excel(writer, sheet_name="SourceFiles", index=False)


# =============================================================================
# Preview
# =============================================================================


def preview_files(
    files: list[Path],
    sheet_name: str | None = None,
    max_files: int = 5,
    max_rows: int = 3,
) -> None:
    """ファイル内容をプレビュー"""
    print("\n" + "=" * 70)
    print("ファイルプレビュー")
    print("=" * 70)

    for file_path in files[:max_files]:
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=max_rows)
            print(f"\nファイル: {file_path.name}")
            print(f"形状: {df.shape}")
            print(f"列: {list(df.columns)}")
            if not df.empty:
                print(df.to_string(index=False))
        except Exception as e:
            print(f"エラー ({file_path.name}): {e}")
        print("-" * 70)

    if len(files) > max_files:
        print(f"\n... 他 {len(files) - max_files} ファイル")


# =============================================================================
# Sample Generator
# =============================================================================


def create_sample_files(output_dir: Path, count: int = 3) -> list[Path]:
    """テスト用サンプルファイルを生成"""
    import random
    from datetime import datetime, timedelta

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for i in range(count):
        filename = output_dir / f"sample_{i + 1}.xlsx"

        data = []
        for j in range(random.randint(50, 200)):
            data.append({
                "ID": j + i * 1000,
                "Name": f"Item_{j + 1}",
                "Category": random.choice(["A", "B", "C"]),
                "Value": random.randint(1, 1000),
                "Date": datetime.now() - timedelta(days=random.randint(0, 365)),
                "Active": random.choice([True, False]),
            })

        df = pd.DataFrame(data)
        df.to_excel(filename, index=False)
        created.append(filename)
        print(f"作成: {filename} ({len(df)}行)")

    return created


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="Excelファイル結合ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s file1.xlsx file2.xlsx -o merged.xlsx
  %(prog)s -d ./data -o output.xlsx --recursive
  %(prog)s -d ./data -o output.csv --add-source --remove-duplicates
  %(prog)s --create-samples ./samples
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="結合するExcelファイル（パターン可）",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="出力ファイルパス",
    )
    parser.add_argument(
        "-d", "--directory",
        type=Path,
        help="検索ディレクトリ",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="サブディレクトリも検索",
    )
    parser.add_argument(
        "-s", "--sheet",
        help="読み込むシート名",
    )
    parser.add_argument(
        "--add-source",
        action="store_true",
        help="ソースファイル名列を追加",
    )
    parser.add_argument(
        "--sort-by",
        metavar="COLUMN",
        help="ソート列",
    )
    parser.add_argument(
        "--remove-duplicates",
        action="store_true",
        help="重複行を削除",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="列互換性チェックをスキップ",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="メタデータシートを追加しない",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="プレビュー表示",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログ",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="ログファイル",
    )

    sample_group = parser.add_argument_group("サンプル生成")
    sample_group.add_argument(
        "--create-samples",
        type=Path,
        metavar="DIR",
        help="サンプルファイルを生成",
    )
    sample_group.add_argument(
        "--sample-count",
        type=int,
        default=3,
        help="サンプル数 (default: 3)",
    )

    return parser.parse_args()


def main() -> int:
    """メインエントリーポイント"""
    args = parse_args()

    # サンプル生成
    if args.create_samples:
        create_sample_files(args.create_samples, args.sample_count)
        return 0

    logger = setup_logging(args.verbose, args.log_file)

    try:
        # ファイル検出
        patterns = args.files or []
        if args.directory:
            patterns.append(str(args.directory))

        if not patterns:
            print("エラー: ファイルまたはディレクトリを指定してください", file=sys.stderr)
            return 1

        files = discover_excel_files(patterns, args.recursive)

        if not files:
            print("エラー: Excelファイルが見つかりません", file=sys.stderr)
            return 1

        print(f"\n見つかったファイル: {len(files)}個")
        for f in files:
            print(f"  {f}")

        # プレビュー
        if args.preview:
            preview_files(files, args.sheet)
            response = input("\n続行しますか? (y/N): ")
            if response.lower() != "y":
                print("中断しました")
                return 0

        # 出力先確認
        if not args.output:
            print("エラー: 出力ファイル (-o) を指定してください", file=sys.stderr)
            return 1

        # 結合実行
        config = MergeConfig(
            output_path=args.output,
            sheet_name=args.sheet,
            add_source_column=args.add_source,
            sort_by=args.sort_by,
            remove_duplicates=args.remove_duplicates,
            validate_columns=not args.no_validate,
            add_metadata_sheet=not args.no_metadata,
        )

        merger = ExcelMerger(config, logger)
        stats = merger.merge(files)

        # 結果表示
        print("\n" + "=" * 50)
        print("処理完了")
        print("=" * 50)
        print(stats.summary())
        print(f"出力: {args.output}")
        print("=" * 50)

        return 0

    except FileNotFoundError as e:
        logger.error("ファイルエラー: %s", e)
        return 1
    except ValueError as e:
        logger.error("設定エラー: %s", e)
        return 1
    except KeyboardInterrupt:
        logger.info("中断されました")
        return 130
    except Exception as e:
        logger.exception("予期しないエラー: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
