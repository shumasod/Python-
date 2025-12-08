#!/usr/bin/env python3
"""
CSV重複削除ツール

大規模CSVファイルの重複行を効率的に削除するCLIツール。
チャンク処理、エンコーディング自動検出、進捗表示に対応。

Usage:
    python csv_dedup.py input.csv output.csv --columns id email
    python csv_dedup.py large.csv out.csv --chunk-size 50000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

import pandas as pd

# =============================================================================
# Types & Configuration
# =============================================================================


class KeepStrategy(Enum):
    """重複保持戦略"""

    FIRST = "first"
    LAST = "last"
    NONE = False


@dataclass(frozen=True)
class DeduplicationConfig:
    """重複削除設定"""

    input_path: Path
    output_path: Path
    subset_columns: tuple[str, ...] | None = None
    keep: Literal["first", "last"] = "first"
    chunk_size: int | None = None
    encoding: str | None = None
    separator: str = ","

    def __post_init__(self) -> None:
        if not self.input_path.exists():
            raise FileNotFoundError(f"入力ファイルが見つかりません: {self.input_path}")


@dataclass
class DeduplicationResult:
    """重複削除結果"""

    original_rows: int
    final_rows: int
    input_path: Path
    output_path: Path
    encoding_used: str

    @property
    def removed_rows(self) -> int:
        return self.original_rows - self.final_rows

    @property
    def duplicate_rate(self) -> float:
        if self.original_rows == 0:
            return 0.0
        return (self.removed_rows / self.original_rows) * 100

    def summary(self) -> str:
        return (
            f"元の行数: {self.original_rows:,}\n"
            f"重複削除後: {self.final_rows:,}\n"
            f"削除された行: {self.removed_rows:,}\n"
            f"重複率: {self.duplicate_rate:.1f}%"
        )


# =============================================================================
# Logging
# =============================================================================


def setup_logging(verbose: bool = False, log_file: Path | None = None) -> logging.Logger:
    """ロガーをセットアップ"""
    logger = logging.getLogger("csv_dedup")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソール
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ファイル（オプション）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# =============================================================================
# Encoding Detection
# =============================================================================


def detect_encoding(file_path: Path, sample_size: int = 65536) -> str:
    """ファイルのエンコーディングを検出"""
    try:
        import chardet

        with open(file_path, "rb") as f:
            raw_data = f.read(sample_size)

        result = chardet.detect(raw_data)
        encoding = result.get("encoding")

        if encoding:
            # 一般的なエンコーディング名を正規化
            encoding_map = {
                "ascii": "utf-8",
                "ISO-8859-1": "cp1252",
                "Windows-1252": "cp1252",
            }
            return encoding_map.get(encoding, encoding)

    except ImportError:
        pass

    return "utf-8"


def get_file_size_mb(path: Path) -> float:
    """ファイルサイズをMB単位で取得"""
    return path.stat().st_size / (1024 * 1024)


# =============================================================================
# Core Deduplication
# =============================================================================


class CsvDeduplicator:
    """CSV重複削除処理"""

    # チャンクサイズ自動決定の閾値
    LARGE_FILE_THRESHOLD_MB = 100
    MEDIUM_FILE_THRESHOLD_MB = 50
    DEFAULT_LARGE_CHUNK = 10000
    DEFAULT_MEDIUM_CHUNK = 50000

    def __init__(self, config: DeduplicationConfig, logger: logging.Logger | None = None) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("csv_dedup")
        self._encoding: str | None = None

    def run(self) -> DeduplicationResult:
        """重複削除を実行"""
        # エンコーディング検出
        self._encoding = self._config.encoding or detect_encoding(self._config.input_path)
        self._logger.info("エンコーディング: %s", self._encoding)

        # ファイルサイズ確認
        file_size = get_file_size_mb(self._config.input_path)
        self._logger.info("入力ファイル: %.2f MB", file_size)

        # チャンクサイズ決定
        chunk_size = self._determine_chunk_size(file_size)

        # 出力ディレクトリ作成
        self._config.output_path.parent.mkdir(parents=True, exist_ok=True)

        # 処理実行
        if chunk_size:
            self._logger.info("チャンク処理モード (chunk_size=%d)", chunk_size)
            return self._process_chunked(chunk_size)
        else:
            self._logger.info("一括処理モード")
            return self._process_single()

    def _determine_chunk_size(self, file_size_mb: float) -> int | None:
        """チャンクサイズを決定"""
        if self._config.chunk_size:
            return self._config.chunk_size

        if file_size_mb > self.LARGE_FILE_THRESHOLD_MB:
            return self.DEFAULT_LARGE_CHUNK
        elif file_size_mb > self.MEDIUM_FILE_THRESHOLD_MB:
            return self.DEFAULT_MEDIUM_CHUNK

        return None

    def _process_single(self) -> DeduplicationResult:
        """一括処理"""
        self._logger.info("ファイル読み込み中...")

        df = pd.read_csv(
            self._config.input_path,
            encoding=self._encoding,
            sep=self._config.separator,
        )
        original_rows = len(df)

        # 列の検証
        self._validate_columns(df)

        # 重複削除
        self._logger.info("重複削除中... (対象列: %s)", self._subset_columns_display)
        df_deduped = df.drop_duplicates(
            subset=list(self._config.subset_columns) if self._config.subset_columns else None,
            keep=self._config.keep,
        )

        # 保存
        self._logger.info("ファイル書き込み中...")
        df_deduped.to_csv(
            self._config.output_path,
            index=False,
            encoding=self._encoding,
            sep=self._config.separator,
        )

        return DeduplicationResult(
            original_rows=original_rows,
            final_rows=len(df_deduped),
            input_path=self._config.input_path,
            output_path=self._config.output_path,
            encoding_used=self._encoding,
        )

    def _process_chunked(self, chunk_size: int) -> DeduplicationResult:
        """チャンク処理"""
        temp_path = self._config.output_path.with_suffix(".tmp")
        original_rows = 0

        try:
            # Phase 1: チャンク内重複削除
            self._logger.info("Phase 1: チャンク内重複削除")
            chunks = pd.read_csv(
                self._config.input_path,
                chunksize=chunk_size,
                encoding=self._encoding,
                sep=self._config.separator,
            )

            is_first = True
            for i, chunk in enumerate(chunks, 1):
                original_rows += len(chunk)
                self._logger.info("  チャンク %d: %d行 (累計: %d)", i, len(chunk), original_rows)

                # 列検証（最初のチャンクのみ）
                if is_first:
                    self._validate_columns(chunk)

                # チャンク内重複削除
                chunk_deduped = chunk.drop_duplicates(
                    subset=list(self._config.subset_columns) if self._config.subset_columns else None,
                    keep=self._config.keep,
                )

                # 一時ファイルに追記
                chunk_deduped.to_csv(
                    temp_path,
                    mode="w" if is_first else "a",
                    header=is_first,
                    index=False,
                    encoding=self._encoding,
                    sep=self._config.separator,
                )
                is_first = False

            # Phase 2: 全体重複削除
            self._logger.info("Phase 2: 全体重複削除")
            df_merged = pd.read_csv(
                temp_path,
                encoding=self._encoding,
                sep=self._config.separator,
            )

            df_final = df_merged.drop_duplicates(
                subset=list(self._config.subset_columns) if self._config.subset_columns else None,
                keep=self._config.keep,
            )

            # 最終出力
            df_final.to_csv(
                self._config.output_path,
                index=False,
                encoding=self._encoding,
                sep=self._config.separator,
            )

            return DeduplicationResult(
                original_rows=original_rows,
                final_rows=len(df_final),
                input_path=self._config.input_path,
                output_path=self._config.output_path,
                encoding_used=self._encoding,
            )

        finally:
            # 一時ファイル削除
            if temp_path.exists():
                temp_path.unlink()

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """指定列の存在を検証"""
        if not self._config.subset_columns:
            return

        missing = [col for col in self._config.subset_columns if col not in df.columns]
        if missing:
            available = ", ".join(df.columns.tolist())
            raise ValueError(
                f"指定された列が見つかりません: {missing}\n"
                f"利用可能な列: {available}"
            )

    @property
    def _subset_columns_display(self) -> str:
        """表示用の列名"""
        if self._config.subset_columns:
            return ", ".join(self._config.subset_columns)
        return "全列"


# =============================================================================
# Sample Data Generator
# =============================================================================


def create_sample_csv(
    output_path: Path,
    rows: int = 1000,
    duplicate_rate: float = 0.3,
) -> None:
    """テスト用サンプルCSVを生成"""
    import random
    import string

    data: list[dict] = []
    unique_id = 0

    for _ in range(rows):
        if data and random.random() < duplicate_rate:
            # 既存行を複製
            data.append(data[random.randint(0, len(data) - 1)].copy())
        else:
            # 新規行
            data.append({
                "id": unique_id,
                "name": "".join(random.choices(string.ascii_letters, k=8)),
                "email": f"user{unique_id}@example.com",
                "score": random.randint(0, 100),
                "category": random.choice(["A", "B", "C"]),
            })
            unique_id += 1

    df = pd.DataFrame(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    actual_duplicates = rows - len(df.drop_duplicates())
    print(f"サンプルファイル作成: {output_path}")
    print(f"  行数: {rows}, 重複行: {actual_duplicates}")


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="CSV重複削除ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s data.csv output.csv
  %(prog)s data.csv output.csv --columns id email
  %(prog)s large.csv out.csv --chunk-size 50000
  %(prog)s --create-sample sample.csv --sample-rows 10000
        """,
    )

    parser.add_argument("input_file", nargs="?", help="入力CSVファイル")
    parser.add_argument("output_file", nargs="?", help="出力CSVファイル")

    parser.add_argument(
        "--columns", "-c",
        nargs="+",
        metavar="COL",
        help="重複判定に使用する列名",
    )
    parser.add_argument(
        "--keep", "-k",
        choices=["first", "last"],
        default="first",
        help="重複時に残す行 (default: first)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        metavar="N",
        help="大規模ファイル用チャンクサイズ",
    )
    parser.add_argument(
        "--encoding", "-e",
        help="ファイルエンコーディング (自動検出)",
    )
    parser.add_argument(
        "--separator", "-s",
        default=",",
        help="CSV区切り文字 (default: ,)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細ログ出力",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="ログファイルパス",
    )

    # サンプル生成
    sample_group = parser.add_argument_group("サンプル生成")
    sample_group.add_argument(
        "--create-sample",
        type=Path,
        metavar="PATH",
        help="サンプルCSVを生成",
    )
    sample_group.add_argument(
        "--sample-rows",
        type=int,
        default=1000,
        help="サンプル行数 (default: 1000)",
    )
    sample_group.add_argument(
        "--sample-dup-rate",
        type=float,
        default=0.3,
        help="サンプル重複率 (default: 0.3)",
    )

    return parser.parse_args()


def main() -> int:
    """メインエントリーポイント"""
    args = parse_args()

    # サンプル生成モード
    if args.create_sample:
        create_sample_csv(
            args.create_sample,
            rows=args.sample_rows,
            duplicate_rate=args.sample_dup_rate,
        )
        return 0

    # 引数検証
    if not args.input_file or not args.output_file:
        print("エラー: 入力ファイルと出力ファイルを指定してください", file=sys.stderr)
        print("ヘルプ: python csv_dedup.py --help", file=sys.stderr)
        return 1

    logger = setup_logging(args.verbose, args.log_file)

    try:
        config = DeduplicationConfig(
            input_path=Path(args.input_file),
            output_path=Path(args.output_file),
            subset_columns=tuple(args.columns) if args.columns else None,
            keep=args.keep,
            chunk_size=args.chunk_size,
            encoding=args.encoding,
            separator=args.separator,
        )

        deduplicator = CsvDeduplicator(config, logger)
        result = deduplicator.run()

        # 結果表示
        print()
        print("=" * 50)
        print("処理完了")
        print("=" * 50)
        print(result.summary())
        print(f"出力: {result.output_path}")
        print("=" * 50)

        return 0

    except FileNotFoundError as e:
        logger.error("ファイルが見つかりません: %s", e)
        return 1
    except ValueError as e:
        logger.error("設定エラー: %s", e)
        return 1
    except pd.errors.EmptyDataError:
        logger.error("入力ファイルが空です")
        return 1
    except pd.errors.ParserError as e:
        logger.error("CSV解析エラー: %s", e)
        return 1
    except KeyboardInterrupt:
        logger.info("処理が中断されました")
        return 130


if __name__ == "__main__":
    sys.exit(main())
