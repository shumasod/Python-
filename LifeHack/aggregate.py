# 11. エクセルデータの集計
def summarize_excel_data(input_file, group_by_column):
    df = pd.read_excel(input_file)
    summary = df.groupby(group_by_column).agg({
        'amount': ['sum', 'mean', 'count'],
        'date': 'max'
    }).round(2)
    return summary
