# 7. ファイル名の一括変更
def batch_rename_files(folder_path, old_text, new_text):
    for filename in os.listdir(folder_path):
        if old_text in filename:
            new_name = filename.replace(old_text, new_text)
            os.rename(os.path.join(folder_path, filename),
                     os.path.join(folder_path, new_name))
