# 3. フォルダ内のファイル整理
import os
import shutil
def organize_files_by_extension(folder_path):
    for filename in os.listdir(folder_path):
        if os.path.isfile(os.path.join(folder_path, filename)):
            extension = filename.split('.')[-1]
            new_folder = os.path.join(folder_path, extension)
            if not os.path.exists(new_folder):
                os.makedirs(new_folder)
            shutil.move(os.path.join(folder_path, filename), 
                       os.path.join(new_folder, filename))
