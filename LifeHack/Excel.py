#!/usr/bin/env python3
"""
Excelファイル結合ツール
複数のExcelファイルを効率的に結合し、様々な結合オプションを提供します。
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union
import pandas as pd
from glob import glob
import warnings

# 警告を抑制
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('excel_merger.log', encoding='utf-8')
        ]
    )


def get_excel_files(patterns: List[str], recursive: bool = False) -> List[str]:
    """指定されたパターンでExcelファイルを取得"""
    excel_files = []
    extensions = ['*.xlsx', '*.xls', '*.xlsm']
    
    for pattern in patterns:
        if os.path.isfile(pattern):
            # 直接ファイルが指定された場合
            excel_files.append(pattern)
        elif os.path.isdir(pattern):
            # ディレクトリが指定された場合
            for ext in extensions:
                search_pattern = os.path.join(pattern, '**', ext) if recursive else os.path.join(pattern, ext)
                excel_files.extend(glob(search_pattern, recursive=recursive))
        else:
            # パターンが指定された場合
            excel_files.extend(glob(pattern, recursive=recursive))
    
    # 重複を削除し、ソート
    excel_files = sorted(list(set(excel_files)))
    logging.info(f"見つかったExcelファイル: {len(excel_files)}個")
    
    return excel_files


def get_sheet_info(file_path: str) -> Dict[str, int]:
    """Excelファイルのシート情報を取得"""
    try:
        excel_file = pd.ExcelFile(file_path)
        sheet_info = {}
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
            sheet_info[sheet_name] = len(df.columns)
        return sheet_info
    except Exception as e:
        logging.warning(f"シート情報取得エラー ({file_path}): {e}")
        return {}


def validate_column_compatibility(file_list: List[str], sheet_name: Optional[str] = None) -> bool:
    """ファイル間の列の互換性をチェック"""
    if not file_list:
        return True
    
    reference_columns = None
    reference_file = None
    
    for file_path in file_list:
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
            else:
                df = pd.read_excel(file_path, nrows=0)
            
            current_columns = list(df.columns)
            
            if reference_columns is None:
                reference_columns = current_columns
                reference_file = file_path
            elif current_columns != reference_columns:
                logging.warning(f"列の構造が異なります:")
                logging.warning(f"  基準ファイル ({reference_file}): {reference_columns}")
                logging.warning(f"  対象ファイル ({file_path}): {current_columns}")
                return False
                
        except Exception as e:
            logging.error(f"ファイル読み込みエラー ({file_path}): {e}")
            return False
    
    return True


def merge_excel_files(
    file_list: List[str],
    output_file: str,
    sheet_name: Optional[str] = None,
    add_source_column: bool = False,
    ignore_index: bool = True,
    sort_by: Optional[str] = None,
    filter_duplicates: bool = False,
    chunk_size: Optional[int] = None,
    validate_columns: bool = True
) -> Dict[str, int]:
    """
    複数のExcelファイルを結合します。

    Args:
        file_list: 結合するExcelファイルのリスト
        output_file: 出力ファイルのパス
        sheet_name: 読み込むシート名（Noneの場合は最初のシート）
        add_source_column: ソースファイル名の列を追加するか
        ignore_index: インデックスを無視するか
        sort_by: ソートする列名
        filter_duplicates: 重複行を削除するか
        chunk_size: 大きなファイル用のチャンクサイズ
        validate_columns: 列の互換性をチェックするか

    Returns:
        処理結果の統計情報
    """
    if not file_list:
        raise ValueError("結合するファイルが指定されていません。")
    
    # ファイルの存在確認
    missing_files = [f for f in file_list if not os.path.exists(f)]
    if missing_files:
        raise FileNotFoundError(f"以下のファイルが見つかりません: {missing_files}")
    
    # 出力ディレクトリの作成
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 列の互換性チェック
    if validate_columns and not validate_column_compatibility(file_list, sheet_name):
        response = input("列の構造が異なるファイルがあります。続行しますか? (y/N): ")
        if response.lower() != 'y':
            raise ValueError("処理を中断しました。")
    
    logging.info("ファイル結合を開始します...")
    
    stats = {
        'total_files': len(file_list),
        'successful_files': 0,
        'failed_files': 0,
        'total_rows': 0,
        'final_rows': 0
    }
    
    dfs = []
    
    for i, file_path in enumerate(file_list, 1):
        try:
            logging.info(f"ファイル {i}/{len(file_list)} を処理中: {os.path.basename(file_path)}")
            
            # Excelファイルの読み込み
            if chunk_size:
                # 大きなファイルの場合はチャンク処理（実際にはExcelでは使用頻度は低い）
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            if df.empty:
                logging.warning(f"空のファイルをスキップ: {file_path}")
                continue
            
            # ソースファイル名を追加
            if add_source_column:
                df['source_file'] = os.path.basename(file_path)
            
            dfs.append(df)
            stats['successful_files'] += 1
            stats['total_rows'] += len(df)
            
            logging.debug(f"  読み込み行数: {len(df):,}")
            
        except Exception as e:
            logging.error(f"ファイル読み込みエラー ({file_path}): {e}")
            stats['failed_files'] += 1
            continue
    
    if not dfs:
        raise ValueError("読み込み可能なファイルがありませんでした。")
    
    # データフレームの結合
    logging.info("データフレームを結合中...")
    try:
        merged_df = pd.concat(dfs, ignore_index=ignore_index, sort=False)
        logging.info(f"結合後の行数: {len(merged_df):,}")
        
        # 重複削除
        if filter_duplicates:
            logging.info("重複行を削除中...")
            before_dedup = len(merged_df)
            merged_df = merged_df.drop_duplicates()
            after_dedup = len(merged_df)
            logging.info(f"重複削除: {before_dedup - after_dedup:,}行削除")
        
        # ソート
        if sort_by and sort_by in merged_df.columns:
            logging.info(f"'{sort_by}'列でソート中...")
            merged_df = merged_df.sort_values(by=sort_by)
        elif sort_by:
            logging.warning(f"ソート列 '{sort_by}' が見つかりません。")
        
        stats['final_rows'] = len(merged_df)
        
        # ファイル出力
        logging.info(f"結果をファイルに保存中: {output_file}")
        
        # 出力形式の判定
        if output_file.endswith('.csv'):
            merged_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        else:
            # Excelファイルとして出力
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                merged_df.to_excel(writer, sheet_name='MergedData', index=False)
                
                # メタデータシートを追加
                metadata = pd.DataFrame({
                    'ファイル名': [os.path.basename(f) for f in file_list],
                    'パス': file_list,
                    '状態': ['成功' if f in [file_list[i] for i in range(stats['successful_files'])] else '失敗' 
                            for f in file_list]
                })
                metadata.to_excel(writer, sheet_name='SourceFiles', index=False)
        
        return stats
        
    except Exception as e:
        logging.error(f"データ結合エラー: {e}")
        raise


def preview_files(file_list: List[str], sheet_name: Optional[str] = None, rows: int = 3) -> None:
    """ファイルの内容をプレビュー表示"""
    print("\n" + "="*80)
    print("ファイルプレビュー")
    print("="*80)
    
    for file_path in file_list[:5]:  # 最初の5ファイルのみ表示
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=rows)
            print(f"\nファイル: {os.path.basename(file_path)}")
            print(f"形状: {df.shape}")
            print(f"列: {list(df.columns)}")
            if not df.empty:
                print("プレビュー:")
                print(df.to_string(index=False))
        except Exception as e:
            print(f"エラー ({file_path}): {e}")
        print("-" * 40)


def create_sample_excel_files(output_dir: str, count: int = 3) -> List[str]:
    """テスト用のサンプルExcelファイルを作成"""
    import random
    from datetime import datetime, timedelta
    
    os.makedirs(output_dir, exist_ok=True)
    created_files = []
    
    for i in range(count):
        filename = os.path.join(output_dir, f"sample_{i+1}.xlsx")
        
        # サンプルデータ作成
        data = []
        for j in range(random.randint(50, 200)):
            data.append({
                'ID': j + i * 1000,
                'Name': f"Item_{j+1}",
                'Category': random.choice(['A', 'B', 'C']),
                'Value': random.randint(1, 1000),
                'Date': datetime.now() - timedelta(days=random.randint(0, 365)),
                'Flag': random.choice([True, False])
            })
        
        df = pd.DataFrame(data)
        df.to_excel(filename, index=False)
        created_files.append(filename)
        logging.info(f"サンプルファイル作成: {filename} ({len(df)}行)")
    
    return created_files


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='Excelファイル結合ツール')
    parser.add_argument('files', nargs='*', help='結合するExcelファイル（パターンも可）')
    parser.add_argument('-o', '--output', required=True, help='出力ファイルのパス')
    parser.add_argument('-s', '--sheet', help='読み込むシート名')
    parser.add_argument('-d', '--directory', help='Excelファイルを検索するディレクトリ')
    parser.add_argument('-r', '--recursive', action='store_true', help='サブディレクトリも検索')
    parser.add_argument('--add-source', action='store_true', help='ソースファイル名の列を追加')
    parser.add_argument('--sort-by', help='ソートする列名')
    parser.add_argument('--remove-duplicates', action='store_true', help='重複行を削除')
    parser.add_argument('--no-validate', action='store_true', help='列の互換性チェックをスキップ')
    parser.add_argument('--preview', action='store_true', help='ファイル内容をプレビュー')
    parser.add_argument('--create-samples', help='指定ディレクトリにサンプルファイルを作成')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログ出力')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # サンプルファイル作成
        if args.create_samples:
            created_files = create_sample_excel_files(args.create_samples)
            print(f"\n{len(created_files)}個のサンプルファイルを作成しました:")
            for f in created_files:
                print(f"  {f}")
            return
        
        # ファイルリストの取得
        file_patterns = args.files or []
        if args.directory:
            file_patterns.append(args.directory)
        
        if not file_patterns:
            raise ValueError("結合するファイルまたはディレクトリを指定してください。")
        
        excel_files = get_excel_files(file_patterns, args.recursive)
        
        if not excel_files:
            raise ValueError("Excelファイルが見つかりませんでした。")
        
        print(f"\n見つかったファイル: {len(excel_files)}個")
        for f in excel_files:
            print(f"  {f}")
        
        # プレビュー表示
        if args.preview:
            preview_files(excel_files, args.sheet)
            response = input("\n続行しますか? (y/N): ")
            if response.lower() != 'y':
                print("処理を中断しました。")
                return
        
        # ファイル結合実行
        stats = merge_excel_files(
            file_list=excel_files,
            output_file=args.output,
            sheet_name=args.sheet,
            add_source_column=args.add_source,
            sort_by=args.sort_by,
            filter_duplicates=args.remove_duplicates,
            validate_columns=not args.no_validate
        )
        
        # 結果表示
        print("\n" + "="*60)
        print("処理結果:")
        print(f"対象ファイル数: {stats['total_files']}")
        print(f"成功: {stats['successful_files']}")
        print(f"失敗: {stats['failed_files']}")
        print(f"総行数: {stats['total_rows']:,}")
        print(f"最終行数: {stats['final_rows']:,}")
        print(f"出力ファイル: {args.output}")
        print("="*60)
        
        logging.info("処理が正常に完了しました。")
        
    except KeyboardInterrupt:
        logging.info("処理が中断されました。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
