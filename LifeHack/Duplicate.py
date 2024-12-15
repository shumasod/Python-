# 4. CSVファイルの重複削除
def remove_duplicates_from_csv(input_file, output_file):
    df = pd.read_csv(input_file)
    df_no_duplicates = df.drop_duplicates()
    df_no_duplicates.to_csv(output_file, index=False)
