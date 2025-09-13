# Python

**初心者から中級者まで対応した実践的なPython学習リソース**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Learning](https://img.shields.io/badge/Level-Beginner%20to%20Intermediate-orange)](README.md)

-----

## 📚 目次

1. [🚀 はじめに](#-はじめに)
1. [📋 前提条件](#-前提条件)
1. [⚡ クイックスタート](#-クイックスタート)
1. [📖 学習コンテンツ](#-学習コンテンツ)
1. [🛠️ 開発環境のセットアップ](#️-開発環境のセットアップ)
1. [💡 学習のコツ](#-学習のコツ)
1. [🤝 コントリビューション](#-コントリビューション)
1. [📄 ライセンス](#-ライセンス)

-----

## 🚀 はじめに

このリポジトリは、Python プログラミングの基礎から実践的なアプリケーション開発まで、段階的に学習できる教材です。各章には理論説明、実例コード、そして実際に手を動かして学べる演習問題が含まれています。

### 🎯 学習目標

このガイドを完了することで、以下のスキルを身につけることができます：

- **基本文法の習得**: 変数、データ型、制御構造の理解
- **データ構造の活用**: リスト、辞書、セットの効果的な使い方
- **関数型プログラミング**: 再利用可能なコードの設計
- **オブジェクト指向プログラミング**: クラスとオブジェクトの概念
- **エラーハンドリング**: 堅牢なプログラムの作成
- **実践的なアプリ開発**: 学んだ知識を統合したプロジェクト作成

-----

## 📋 前提条件

### 必要なもの

- **Python 3.9以上** （推奨: Python 3.11+）
- **テキストエディタまたはIDE** （推奨: VS Code, PyCharm）
- **基本的なコンピュータ操作の知識**

### 推奨環境

```bash
# Python バージョン確認
python --version  # または python3 --version

# pip のアップデート
pip install --upgrade pip
```

-----

## ⚡ クイックスタート

### 1分で始める Python

```python
# hello_world.py
def main():
    name = input("お名前を教えてください: ")
    print(f"こんにちは、{name}さん！🎉")
    print("Python学習をはじめましょう！")

if __name__ == "__main__":
    main()
```

```bash
# 実行方法
python hello_world.py
```

-----

## 📖 学習コンテンツ

### 第1章: プログラミングの基礎 🎯

**所要時間: 30分**

プログラミングとは何か、Pythonの特徴、そして最初のプログラムを作成します。

```python
# モダンなPythonの書き方
from typing import Optional

def greet_user(name: str, greeting: Optional[str] = None) -> str:
    """ユーザーに挨拶メッセージを返す
    
    Args:
        name: ユーザーの名前
        greeting: カスタム挨拶（オプション）
    
    Returns:
        挨拶メッセージ
    """
    default_greeting = "こんにちは"
    message = greeting or default_greeting
    return f"{message}、{name}さん！"

# 使用例
print(greet_user("太郎"))
print(greet_user("花子", "おはよう"))
```

**🏃‍♂️ 実習課題**

1. 自己紹介プログラムの作成
1. 計算機能付きプログラムの実装

-----

### 第2章: 変数とデータ型 📦

**所要時間: 45分**

型ヒント、f-string、そして現代的なPythonのデータ操作について学習します。

```python
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Union

@dataclass
class Student:
    """学生情報を管理するデータクラス"""
    name: str
    age: int
    grade: float
    subjects: List[str]
    
    def get_grade_letter(self) -> str:
        """成績を文字で返す"""
        if self.grade >= 90: return "A"
        elif self.grade >= 80: return "B"
        elif self.grade >= 70: return "C"
        else: return "D"

# 使用例
student = Student("田中太郎", 16, 85.5, ["数学", "物理", "化学"])
print(f"{student.name}さんの成績: {student.get_grade_letter()}")
```

**📊 Pythonの主要データ型（2024年版）**

|型      |説明    |例                 |用途        |
|-------|------|------------------|----------|
|`str`  |文字列   |`"Hello World"`   |テキスト処理    |
|`int`  |整数    |`42`              |数値計算      |
|`float`|浮動小数点数|`3.14159`         |科学計算      |
|`bool` |真偽値   |`True`, `False`   |条件判定      |
|`list` |リスト   |`[1, 2, 3]`       |順序付きデータ   |
|`dict` |辞書    |`{"key": "value"}`|キー・バリューペア |
|`set`  |セット   |`{1, 2, 3}`       |重複なしコレクション|

-----

### 第3章: データ構造とアルゴリズム 🗂️

**所要時間: 60分**

効率的なデータ操作と、Pythonらしいコードの書き方を学習します。

```python
from collections import defaultdict, Counter
from typing import List, Dict, Tuple

class DataProcessor:
    """データ処理を行うクラス"""
    
    @staticmethod
    def analyze_scores(scores: List[int]) -> Dict[str, Union[float, int]]:
        """スコアデータの統計分析"""
        if not scores:
            return {}
            
        return {
            "平均": sum(scores) / len(scores),
            "最大": max(scores),
            "最小": min(scores),
            "合計": sum(scores),
            "データ数": len(scores)
        }
    
    @staticmethod
    def group_by_grade(students: List[Dict]) -> Dict[str, List[str]]:
        """成績別に学生をグループ化"""
        groups = defaultdict(list)
        
        for student in students:
            grade = student.get("grade", 0)
            name = student.get("name", "不明")
            
            if grade >= 90:
                groups["優秀"].append(name)
            elif grade >= 70:
                groups["良好"].append(name)
            else:
                groups["要改善"].append(name)
        
        return dict(groups)

# 使用例
test_scores = [85, 92, 78, 96, 73, 88, 91]
analysis = DataProcessor.analyze_scores(test_scores)
print("スコア分析結果:")
for key, value in analysis.items():
    print(f"  {key}: {value}")
```

**🎯 リスト内包表記とジェネレータ**

```python
# 従来の書き方
squares = []
for i in range(10):
    if i % 2 == 0:
        squares.append(i ** 2)

# Pythonらしい書き方
squares = [i ** 2 for i in range(10) if i % 2 == 0]

# メモリ効率的なジェネレータ
squares_generator = (i ** 2 for i in range(10) if i % 2 == 0)
```

-----

### 第4章: 制御構造とフロー制御 🔄

**所要時間: 45分**

条件分岐、ループ、そして例外処理について学習します。

```python
import sys
from pathlib import Path
from typing import Generator, Optional

class FileProcessor:
    """ファイル処理クラス"""
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
    
    def find_python_files(self) -> Generator[Path, None, None]:
        """Python ファイルを再帰的に検索"""
        try:
            for file_path in self.base_path.rglob("*.py"):
                if file_path.is_file():
                    yield file_path
        except PermissionError as e:
            print(f"アクセス権限エラー: {e}")
        except Exception as e:
            print(f"予期しないエラー: {e}")
    
    def count_lines(self, file_path: Path) -> Optional[int]:
        """ファイルの行数をカウント"""
        try:
            with file_path.open('r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except (UnicodeDecodeError, FileNotFoundError) as e:
            print(f"ファイル読み込みエラー ({file_path}): {e}")
            return None

# 使用例: プロジェクト内のPythonファイル統計
def analyze_project():
    processor = FileProcessor()
    total_files = 0
    total_lines = 0
    
    print("🔍 Python ファイルを分析中...")
    
    for py_file in processor.find_python_files():
        line_count = processor.count_lines(py_file)
        
        if line_count is not None:
            total_files += 1
            total_lines += line_count
            print(f"  📄 {py_file.name}: {line_count} 行")
    
    print(f"\n📊 分析結果:")
    print(f"  ファイル数: {total_files}")
    print(f"  総行数: {total_lines}")
    print(f"  平均行数: {total_lines / total_files if total_files > 0 else 0:.1f}")

if __name__ == "__main__":
    analyze_project()
```

-----

### 第5章: 関数と関数型プログラミング ⚡

**所要時間: 50分**

高階関数、デコレータ、そして関数型プログラミングの概念を学習します。

```python
import functools
import time
from typing import Callable, Any, List
from dataclasses import dataclass

def timing_decorator(func: Callable) -> Callable:
    """実行時間を測定するデコレータ"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        
        print(f"⏱️  {func.__name__} 実行時間: {end_time - start_time:.4f} 秒")
        return result
    return wrapper

@dataclass
class Task:
    """タスク情報"""
    name: str
    priority: int
    completed: bool = False

class TaskManager:
    """タスク管理クラス"""
    
    def __init__(self):
        self.tasks: List[Task] = []
    
    @timing_decorator
    def add_task(self, name: str, priority: int = 1):
        """タスクを追加"""
        self.tasks.append(Task(name, priority))
        print(f"✅ タスク追加: {name}")
    
    def get_tasks_by_priority(self) -> List[Task]:
        """優先度順でタスクを取得"""
        return sorted(self.tasks, key=lambda task: task.priority, reverse=True)
    
    def get_pending_tasks(self) -> List[Task]:
        """未完了タスクを取得"""
        return list(filter(lambda task: not task.completed, self.tasks))
    
    def complete_task(self, task_name: str) -> bool:
        """タスクを完了に変更"""
        for task in self.tasks:
            if task.name == task_name:
                task.completed = True
                print(f"🎉 タスク完了: {task_name}")
                return True
        return False

# 使用例
manager = TaskManager()
manager.add_task("Python学習", 3)
manager.add_task("プロジェクト企画", 2)
manager.add_task("買い物", 1)

print("\n📋 優先度順タスクリスト:")
for task in manager.get_tasks_by_priority():
    status = "✅" if task.completed else "⏳"
    print(f"  {status} {task.name} (優先度: {task.priority})")
```

-----

### 第6章: オブジェクト指向プログラミング 🏗️

**所要時間: 70分**

クラス設計、継承、ポリモーフィズム、そして設計パターンについて学習します。

```python
from abc import ABC, abstractmethod
from typing import List, Protocol
from dataclasses import dataclass
from enum import Enum

class PaymentMethod(Enum):
    """支払い方法の列挙型"""
    CASH = "現金"
    CREDIT_CARD = "クレジットカード"
    DIGITAL = "電子マネー"

@dataclass
class Product:
    """商品クラス"""
    name: str
    price: float
    category: str
    
    def __post_init__(self):
        if self.price < 0:
            raise ValueError("価格は0以上である必要があります")

class PaymentProcessor(Protocol):
    """支払い処理のプロトコル"""
    def process_payment(self, amount: float) -> bool:
        ...

class CashPayment:
    """現金支払い処理"""
    def process_payment(self, amount: float) -> bool:
        print(f"💵 現金で {amount:,.0f}円 を支払いました")
        return True

class CreditCardPayment:
    """クレジットカード支払い処理"""
    def __init__(self, card_number: str):
        self.card_number = card_number[-4:]  # 下4桁のみ保存
    
    def process_payment(self, amount: float) -> bool:
        print(f"💳 カード(****{self.card_number})で {amount:,.0f}円 を支払いました")
        return True

class ShoppingCart:
    """ショッピングカートクラス"""
    
    def __init__(self):
        self.items: List[Product] = []
        self.payment_processor: PaymentProcessor = CashPayment()
    
    def add_item(self, product: Product, quantity: int = 1):
        """商品をカートに追加"""
        for _ in range(quantity):
            self.items.append(product)
        print(f"🛒 {product.name} × {quantity} をカートに追加しました")
    
    def calculate_total(self) -> float:
        """合計金額を計算"""
        return sum(item.price for item in self.items)
    
    def set_payment_method(self, processor: PaymentProcessor):
        """支払い方法を設定"""
        self.payment_processor = processor
    
    def checkout(self) -> bool:
        """精算処理"""
        if not self.items:
            print("❌ カートが空です")
            return False
        
        total = self.calculate_total()
        print(f"\n🧾 ご購入明細:")
        
        # カテゴリ別集計
        from collections import defaultdict
        category_totals = defaultdict(float)
        
        for item in self.items:
            category_totals[item.category] += item.price
        
        for category, amount in category_totals.items():
            print(f"  {category}: {amount:,.0f}円")
        
        print(f"  合計: {total:,.0f}円")
        print("-" * 30)
        
        # 支払い処理
        return self.payment_processor.process_payment(total)

# 使用例: ECサイトのシミュレーション
def shopping_simulation():
    # 商品作成
    products = [
        Product("Python入門書", 2500, "書籍"),
        Product("ワイヤレスマウス", 1200, "PC周辺機器"),
        Product("コーヒー豆", 800, "食品"),
    ]
    
    # ショッピング
    cart = ShoppingCart()
    
    for product in products:
        cart.add_item(product)
    
    # 支払い方法設定
    card_payment = CreditCardPayment("1234-5678-9012-3456")
    cart.set_payment_method(card_payment)
    
    # 精算
    success = cart.checkout()
    
    if success:
        print("\n🎉 購入完了！ありがとうございました。")
    else:
        print("\n❌ 購入に失敗しました。")

if __name__ == "__main__":
    shopping_simulation()
```

-----

### 第7章: エラーハンドリングと品質管理 🛡️

**所要時間: 40分**

例外処理、ログ記録、テスト、そしてコード品質について学習します。

```python
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """設定エラー"""
    pass

class DataValidationError(Exception):
    """データ検証エラー"""
    pass

class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """設定ファイルを読み込み"""
        try:
            if self.config_path.exists():
                with self.config_path.open('r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"設定ファイルを読み込みました: {self.config_path}")
            else:
                self._create_default_config()
        except json.JSONDecodeError as e:
            raise ConfigError(f"設定ファイルの形式が正しくありません: {e}")
        except Exception as e:
            raise ConfigError(f"設定ファイルの読み込みに失敗しました: {e}")
    
    def _create_default_config(self):
        """デフォルト設定を作成"""
        default_config = {
            "app_name": "Python学習アプリ",
            "version": "1.0.0",
            "debug": False,
            "max_users": 100,
            "features": {
                "logging": True,
                "auto_save": True
            }
        }
        
        try:
            with self.config_path.open('w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            
            self.config = default_config
            logger.info("デフォルト設定ファイルを作成しました")
            
        except Exception as e:
            logger.error(f"デフォルト設定の作成に失敗: {e}")
            raise ConfigError(f"設定ファイルの作成に失敗しました: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """設定値を更新"""
        self.config[key] = value
        self._save_config()
    
    def _save_config(self):
        """設定をファイルに保存"""
        try:
            with self.config_path.open('w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("設定ファイルを保存しました")
        except Exception as e:
            logger.error(f"設定ファイルの保存に失敗: {e}")

@contextmanager
def safe_operation(operation_name: str):
    """安全な操作のコンテキストマネージャ"""
    logger.info(f"操作開始: {operation_name}")
    try:
        yield
        logger.info(f"操作完了: {operation_name}")
    except Exception as e:
        logger.error(f"操作失敗: {operation_name} - {e}")
        raise
    finally:
        logger.debug(f"操作終了: {operation_name}")

# 使用例: エラーハンドリングの実践
def demo_error_handling():
    """エラーハンドリングのデモ"""
    
    with safe_operation("設定管理テスト"):
        try:
            config = ConfigManager("test_config.json")
            
            # 設定の取得
            app_name = config.get("app_name", "デフォルトアプリ")
            print(f"📱 アプリ名: {app_name}")
            
            # 設定の更新
            config.set("last_run", "2024-01-01")
            
        except ConfigError as e:
            print(f"❌ 設定エラー: {e}")
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
            logger.exception("予期しないエラーが発生しました")

if __name__ == "__main__":
    demo_error_handling()
```

-----

### 第8章: 総合演習プロジェクト 🚀

**所要時間: 120分**

これまで学んだ知識を統合して、実用的なアプリケーションを作成します。

```python
#!/usr/bin/env python3
"""
タスク管理システム v2.0
- GUI版タスク管理アプリケーション
- データベース連携
- ユーザー認証
- レポート機能
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class User:
    """ユーザー情報"""
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    created_at: Optional[datetime] = None

@dataclass
class Task:
    """タスク情報"""
    id: Optional[int] = None
    user_id: int = 0
    title: str = ""
    description: str = ""
    priority: int = 1
    completed: bool = False
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Database:
    """データベース管理クラス"""
    
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """データベース初期化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority INTEGER DEFAULT 1,
                    completed BOOLEAN DEFAULT FALSE,
                    due_date DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            conn.commit()

class TaskManager:
    """タスク管理システム"""
    
    def __init__(self, db_path: str = "tasks.db"):
        self.db = Database(db_path)
        self.current_user: Optional[User] = None
    
    def hash_password(self, password: str) -> str:
        """パスワードをハッシュ化"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, email: str, password: str) -> bool:
        """新しいユーザーを作成"""
        try:
            password_hash = self.hash_password(password)
            
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash)
                )
                conn.commit()
            
            print(f"✅ ユーザー '{username}' を作成しました")
            return True
            
        except sqlite3.IntegrityError:
            print("❌ ユーザー名またはメールアドレスが既に使用されています")
            return False
    
    def login(self, username: str, password: str) -> bool:
        """ユーザーログイン"""
        password_hash = self.hash_password(password)
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            )
            row = cursor.fetchone()
            
            if row:
                self.current_user = User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    password_hash=row[3],
                    created_at=datetime.fromisoformat(row[4])
                )
                print(f"🎉 {username}さん、おかえりなさい！")
                return True
            else:
                print("❌ ユーザー名またはパスワードが正しくありません")
                return False
    
    def add_task(self, title: str, description: str = "", priority: int = 1, 
                 due_date: Optional[datetime] = None) -> bool:
        """タスクを追加"""
        if not self.current_user:
            print("❌ ログインが必要です")
            return False
        
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    """INSERT INTO tasks 
                       (user_id, title, description, priority, due_date) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (self.current_user.id, title, description, priority, due_date)
                )
                conn.commit()
            
            print(f"📝 タスク '{title}' を追加しました")
            return True
            
        except Exception as e:
            print(f"❌ タスクの追加に失敗しました: {e}")
            return False
    
    def get_tasks(self, completed: Optional[bool] = None) -> List[Task]:
        """タスク一覧を取得"""
        if not self.current_user:
            return []
        
        query = "SELECT * FROM tasks WHERE user_id = ?"
        params = [self.current_user.id]
        
        if completed is not None:
            query += " AND completed = ?"
            params.append(completed)
        
        query += " ORDER BY priority DESC, created_at DESC"
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                task = Task(
                    id=row[0],
                    user_id=row[1],
                    title=row[2],
                    description=row[3],
                    priority=row[4],
                    completed=bool(row[5]),
                    due_date=datetime.fromisoformat(row[6]) if row[6] else None,
                    created_at=datetime.fromisoformat(row[7]),
                    updated_at=datetime.fromisoformat(row[8])
```