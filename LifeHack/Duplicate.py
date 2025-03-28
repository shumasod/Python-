import os
from typing import Tuple, Optional
import pandas as pd

def remove_duplicates_from_csv(
    input_file: str, 
    output_file: str, 
    chunk_size: Optional[int] = None
) -> Tuple[int, int, int]:
    """CSVファイルから重複行を削除し、結果を新しいファイルに保存します。

    Args:
        input_file (str): 入力CSVファイルのパス
        output_file (str): 重複を削除した出力CSVファイルのパス
        chunk_size (Optional[int]): 大きなファイルを処理する際のチャンクサイズ

    Returns:
        Tuple[int, int, int]: (元の行数, 重複削除後の行数, 削除された行数)

    Raises:
        ValueError: 入力値が無効な場合
        FileNotFoundError: 入力ファイルが存在しない、または出力ディレクトリが存在しない場合
        Exception: ファイルの読み書きに関するその他のエラー
    """
    # 引数のバリデーション
    if not input_file or not output_file:
        raise ValueError("入力ファイルと出力ファイルのパスを指定してください。")
    
    # 入力ファイルの存在確認
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"入力ファイル '{input_file}' が見つかりません。")
    
    # 出力ディレクトリの存在確認
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        raise FileNotFoundError(f"出力ディレクトリ '{output_dir}' が存在しません。")

    try:
        print(f"ファイル読み込み中: {input_file}")
        
        if chunk_size:
            # 大きなファイル用の処理
            return _process_large_file(input_file, output_file, chunk_size)
        else:
            # 通常の処理
            return _process_normal_file(input_file, output_file)

    except pd.errors.EmptyDataError:
        raise ValueError(f"入力ファイル '{input_file}' が空です。")
    except pd.errors.ParserError:
        raise ValueError(f"'{input_file}' の解析エラー。有効なCSVファイルか確認してください。")
    except Exception as e:
        raise Exception(f"ファイル処理中にエラーが発生しました: {e}")

def _process_normal_file(input_file: str, output_file: str) -> Tuple[int, int, int]:
    """通常サイズのファイルを処理します。"""
    df = pd.read_csv(input_file)
    initial_rows = len(df)
    
    print("重複行を削除中...")
    df_no_duplicates = df.drop_duplicates()
    final_rows = len(df_no_duplicates)
    removed_rows = initial_rows - final_rows
    
    print(f"ファイルに書き込み中: {output_file}")
    df_no_duplicates.to_csv(output_file, index=False)
    
    return initial_rows, final_rows, removed_rows

def _process_large_file(input_file: str, output_file: str, chunk_size: int) -> Tuple[int, int, int]:
    """大きなファイルをチャンク単位で処理します。"""
    initial_rows = 0
    final_rows = 0
    
    # 最初のチャンクを処理
    chunks = pd.read_csv(input_file, chunksize=chunk_size)
    first_chunk = True
    
    for chunk in chunks:
        initial_rows += len(chunk)
        
        print(f"チャンク処理中... (現在の行数: {initial_rows})")
        chunk_no_duplicates = chunk.drop_duplicates()
        
        # 最初のチャンクは新規作成、以降は追記
        mode = 'w' if first_chunk else 'a'
        header = first_chunk
        chunk_no_duplicates.to_csv(output_file, mode=mode, header=header, index=False)
        first_chunk = False
    
    # 最終的な重複削除
    print("最終的な重複チェックを実行中...")
    final_df = pd.read_csv(output_file)
    final_df_no_duplicates = final_df.drop_duplicates()
    final_rows = len(final_df_no_duplicates)
    
    # 最終結果を保存
    final_df_no_duplicates.to_csv(output_file, index=False)
    removed_rows = initial_rows - final_rows
    
    return initial_rows, final_rows, removed_rows

def main():
    """メイン実行関数"""
    try:
        input_file = "input.csv"  # 入力ファイル名を設定
        output_file = "output.csv"  # 出力ファイル名を設定
        
        # ファイルサイズに基づいてchunk_sizeを決定
        file_size = os.path.getsize(input_file)
        chunk_size = 100000 if file_size > 1e8 else None  # 100MB以上の場合はチャンク処理
        
        # 重複削除の実行
        initial_rows, final_rows, removed_rows = remove_duplicates_from_csv(
            input_file, output_file, chunk_size
        )
        
        # 結果の表示
        print("\n処理結果:")
        print(f"元の行数: {initial_rows:,}")
        print(f"重複削除後の行数: {final_rows:,}")
        print(f"削除された重複行: {removed_rows:,}")
        print(f"重複率: {(removed_rows/initial_rows*100):.1f}%")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise

if __name__ == "__main__":
    main()
