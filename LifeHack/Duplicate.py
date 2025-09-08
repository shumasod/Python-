#!/usr/bin/env python3


import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Tuple, Optional, List
import pandas as pd


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('csv_dedup.log', encoding='utf-8')
        ]
    )


def get_file_size_mb(file_path: str) -> float:
    """ファイルサイズをMB単位で取得"""
    return os.path.getsize(file_path) / (1024 * 1024)


def detect_encoding(file_path: str) -> str:
    """ファイルの文字エンコーディングを検出"""
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # 最初の10KBを読み取り
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    except ImportError:
        logging.warning("chardetが利用できません。utf-8を使用します。")
        return 'utf-8'


def remove_duplicates_from_csv(
    input_file: str,
    output_file: str,
    subset_columns: Optional[List[str]] = None,
    keep: str = 'first',
    chunk_size: Optional[int] = None,
    encoding: Optional[str] = None,
    sep: str = ','
) -> Tuple[int, int, int]:
    """CSVファイルから重複行を削除し、結果を新しいファイルに保存します。

    Args:
        input_file (str): 入力CSVファイルのパス
        output_file (str): 重複を削除した出力CSVファイルのパス
        subset_columns (Optional[List[str]]): 重複判定に使用する列名のリスト
        keep (str): 重複時に残す行 ('first', 'last', False)
        chunk_size (Optional[int]): 大きなファイルを処理する際のチャンクサイズ
        encoding (Optional[str]): ファイルの文字エンコーディング
        sep (str): CSV区切り文字

    Returns:
        Tuple[int, int, int]: (元の行数, 重複削除後の行数, 削除された行数)
    """
    # 引数のバリデーション
    if not input_file or not output_file:
        raise ValueError("入力ファイルと出力ファイルのパスを指定してください。")
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    # 入力ファイルの存在確認
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイル '{input_file}' が見つかりません。")
    
    # 出力ディレクトリの作成
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # エンコーディングの自動検出
    if encoding is None:
        encoding = detect_encoding(input_file)
        logging.info(f"検出されたエンコーディング: {encoding}")
    
    # ファイルサイズの確認
    file_size_mb = get_file_size_mb(input_file)
    logging.info(f"入力ファイルサイズ: {file_size_mb:.2f} MB")
    
    # チャンクサイズの自動決定
    if chunk_size is None:
        if file_size_mb > 100:  # 100MB以上
            chunk_size = 10000
            logging.info(f"大きなファイルのため、チャンク処理を使用します (chunk_size: {chunk_size})")
        elif file_size_mb > 50:  # 50MB以上
            chunk_size = 50000
    
    try:
        if chunk_size:
            return _process_large_file(
                input_file, output_file, subset_columns, keep, 
                chunk_size, encoding, sep
            )
        else:
            return _process_normal_file(
                input_file, output_file, subset_columns, keep, encoding, sep
            )
    
    except pd.errors.EmptyDataError:
        raise ValueError(f"入力ファイル '{input_file}' が空です。")
    except pd.errors.ParserError as e:
        raise ValueError(f"'{input_file}' の解析エラー: {e}")
    except Exception as e:
        logging.error(f"ファイル処理中にエラーが発生: {e}")
        raise


def _process_normal_file(
    input_file: str, output_file: str, subset_columns: Optional[List[str]],
    keep: str, encoding: str, sep: str
) -> Tuple[int, int, int]:
    """通常サイズのファイルを処理します。"""
    logging.info(f"ファイル読み込み中: {input_file}")
    
    df = pd.read_csv(input_file, encoding=encoding, sep=sep)
    initial_rows = len(df)
    
    # 指定された列が存在するかチェック
    if subset_columns:
        missing_cols = [col for col in subset_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"指定された列が見つかりません: {missing_cols}")
    
    logging.info(f"重複行を削除中... (対象列: {subset_columns or '全列'})")
    df_no_duplicates = df.drop_duplicates(subset=subset_columns, keep=keep)
    final_rows = len(df_no_duplicates)
    removed_rows = initial_rows - final_rows
    
    logging.info(f"ファイルに書き込み中: {output_file}")
    df_no_duplicates.to_csv(output_file, index=False, encoding=encoding, sep=sep)
    
    return initial_rows, final_rows, removed_rows


def _process_large_file(
    input_file: str, output_file: str, subset_columns: Optional[List[str]],
    keep: str, chunk_size: int, encoding: str, sep: str
) -> Tuple[int, int, int]:
    """大きなファイルをチャンク単位で処理します。"""
    initial_rows = 0
    temp_file = f"{output_file}.tmp"
    
    logging.info("チャンク処理を開始します...")
    
    try:
        # チャンク単位で処理
        chunks = pd.read_csv(input_file, chunksize=chunk_size, encoding=encoding, sep=sep)
        first_chunk = True
        
        for i, chunk in enumerate(chunks):
            initial_rows += len(chunk)
            logging.info(f"チャンク {i+1} 処理中... (行数: {len(chunk)}, 累計: {initial_rows})")
            
            # 各チャンク内の重複削除
            chunk_no_duplicates = chunk.drop_duplicates(subset=subset_columns, keep=keep)
            
            # 一時ファイルに保存
            mode = 'w' if first_chunk else 'a'
            header = first_chunk
            chunk_no_duplicates.to_csv(
                temp_file, mode=mode, header=header, index=False, 
                encoding=encoding, sep=sep
            )
            first_chunk = False
        
        # 全体での重複削除
        logging.info("全体での重複チェックを実行中...")
        final_df = pd.read_csv(temp_file, encoding=encoding, sep=sep)
        final_df_no_duplicates = final_df.drop_duplicates(subset=subset_columns, keep=keep)
        final_rows = len(final_df_no_duplicates)
        
        # 最終結果を保存
        final_df_no_duplicates.to_csv(output_file, index=False, encoding=encoding, sep=sep)
        removed_rows = initial_rows - final_rows
        
        # 一時ファイルを削除
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return initial_rows, final_rows, removed_rows
    
    except Exception as e:
        # エラー時は一時ファイルを削除
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise e


def create_sample_csv(filename: str, rows: int = 1000, duplicate_rate: float = 0.3):
    """テスト用のサンプルCSVファイルを作成"""
    import random
    import string
    
    data = []
    for i in range(rows):
        if random.random() < duplicate_rate and i > 0:
            # 既存の行を複製
            data.append(data[random.randint(0, len(data)-1)])
        else:
            # 新しい行を作成
            data.append({
                'id': i,
                'name': ''.join(random.choices(string.ascii_letters, k=8)),
                'email': f"user{i}@example.com",
                'score': random.randint(0, 100)
            })
    
    pd.DataFrame(data).to_csv(filename, index=False)
    logging.info(f"サンプルファイルを作成しました: {filename}")


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='CSV重複削除ツール')
    parser.add_argument('input_file', help='入力CSVファイルのパス')
    parser.add_argument('output_file', help='出力CSVファイルのパス')
    parser.add_argument('--columns', nargs='+', help='重複判定に使用する列名')
    parser.add_argument('--keep', choices=['first', 'last'], default='first',
                       help='重複時に残す行 (デフォルト: first)')
    parser.add_argument('--chunk-size', type=int, help='チャンクサイズ')
    parser.add_argument('--encoding', help='ファイルエンコーディング')
    parser.add_argument('--sep', default=',', help='CSV区切り文字 (デフォルト: ,)')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログ出力')
    parser.add_argument('--create-sample', help='指定したファイル名でサンプルCSVを作成')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # サンプルファイル作成
        if args.create_sample:
            create_sample_csv(args.create_sample)
            return
        
        # 重複削除の実行
        logging.info("CSV重複削除処理を開始します...")
        initial_rows, final_rows, removed_rows = remove_duplicates_from_csv(
            args.input_file,
            args.output_file,
            subset_columns=args.columns,
            keep=args.keep,
            chunk_size=args.chunk_size,
            encoding=args.encoding,
            sep=args.sep
        )
        
        # 結果の表示
        print("\n" + "="*50)
        print("処理結果:")
        print(f"元の行数: {initial_rows:,}")
        print(f"重複削除後の行数: {final_rows:,}")
        print(f"削除された重複行: {removed_rows:,}")
        print(f"重複率: {(removed_rows/initial_rows*100):.1f}%")
        print(f"出力ファイル: {args.output_file}")
        print("="*50)
        
        logging.info("処理が正常に完了しました。")
        
    except KeyboardInterrupt:
        logging.info("処理が中断されました。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
