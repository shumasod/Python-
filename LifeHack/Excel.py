# 1. エクセルファイルの結合
import pandas as pd
def merge_excel_files(file_list, output_file):
    dfs = []
    for file in file_list:
        df = pd.read_excel(file)
        dfs.append(df)
    merged_df = pd.concat(dfs)
    merged_df.to_excel(output_file, index=False)
