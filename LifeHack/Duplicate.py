import os
import pandas as pd

def remove_duplicates_from_csv(input_file: str, output_file: str) -> None:
    """Removes duplicate rows from a CSV file and saves the result to a new file.

    Args:
        input_file (str): Path to the input CSV file.
        output_file (str): Path to the output CSV file without duplicates.

    Raises:
        FileNotFoundError: If the input file does not exist.
        Exception: For other errors such as issues with reading or writing the file.
    """
    # 入力ファイルが存在するかチェック
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file '{input_file}' does not exist.")

    try:
        # CSVファイルを読み込み
        df = pd.read_csv(input_file)
    except Exception as e:
        raise Exception(f"Error reading the input file: {e}")

    try:
        # 重複行を削除
        df_no_duplicates = df.drop_duplicates()

        # 結果をCSVファイルに保存
        df_no_duplicates.to_csv(output_file, index=False)
        print(f"Duplicates removed successfully. Output saved to '{output_file}'.")
    except Exception as e:
        raise Exception(f"Error writing to the output file: {e}")
