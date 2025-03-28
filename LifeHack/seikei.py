# 8. エクセルの表を整形
def format_excel_table(input_file, output_file):
    df = pd.read_excel(input_file)
    writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    writer.close()
