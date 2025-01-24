import os
from datetime import datetime
from enum import Enum
import gzip
import shutil

class LogLevel(Enum):
    INFO = 1
    WARN = 2
    ERROR = 3

class Logger:
    def __init__(self, file_path, max_size_mb=10, backup_count=5):
        self.file_path = file_path
        self.max_size = max_size_mb * 1024 * 1024  # Convert MB to bytes
        self.backup_count = backup_count
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
    def _should_rotate(self):
        try:
            return os.path.getsize(self.file_path) >= self.max_size
        except OSError:
            return False
            
    def _rotate(self):
        if not os.path.exists(self.file_path):
            return
            
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{self.file_path}.{i}.gz" if i > 0 else self.file_path
            dst = f"{self.file_path}.{i + 1}.gz"
            
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                if i == 0:
                    with open(src, 'rb') as f_in:
                        with gzip.open(dst, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                else:
                    shutil.move(src, dst)
                    
        # Remove original file
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
            
    def log(self, level: LogLevel, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {level.name}: {message}\n"
        
        if self._should_rotate():
            self._rotate()
            
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            
    def info(self, message: str):
        self.log(LogLevel.INFO, message)
        
    def warn(self, message: str):
        self.log(LogLevel.WARN, message)
        
    def error(self, message: str):
        self.log(LogLevel.ERROR, message)

# 使用例
if __name__ == "__main__":
    logger = Logger("logs/app.log", max_size_mb=1, backup_count=3)
    
    logger.info("アプリケーションを開始しました")
    logger.warn("メモリ使用量が高くなっています")
    logger.error("データベース接続に失敗しました")
