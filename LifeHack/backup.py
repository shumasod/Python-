# 6. 定期的なバックアップ
import datetime
def backup_files(source_dir, backup_dir):
    date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_folder = os.path.join(backup_dir, f'backup_{date_str}')
    shutil.copytree(source_dir, backup_folder)
