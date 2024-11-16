# Pythonプログラミング基礎ガイド

## 1. データ型と変数

### 解説
Pythonは動的型付け言語です。これは、変数の型を明示的に宣言する必要がなく、代入される値に基づいて自動的に型が決定されることを意味します。ただし、型ヒントを使用することで、コードの可読性と保守性を向上させることができます。

### 基本データ型の特徴
- **int（整数型）**: 整数値を表現します。Pythonでは、整数のサイズは実質的に無制限です。
- **float（浮動小数点型）**: 小数値を表現します。IEEE 754倍精度浮動小数点数を使用します。
- **str（文字列型）**: テキストデータを表現します。Pythonの文字列はイミュータブル（変更不可）です。
- **bool（真偽値型）**: `True`または`False`の2つの値のみを持ちます。
- **None型**: 値が存在しないことを表現する特殊な型です。

```python
# データ型の基本的な使用例
x = 42  # 整数型
y = 3.14  # 浮動小数点型
name = "Python"  # 文字列型
is_active = True  # 真偽値型
empty = None  # None型

# 型の確認
print(f"xの型: {type(x)}")  # <class 'int'>
print(f"yの型: {type(y)}")  # <class 'float'>

# 文字列操作の例
text = "Hello, Python!"
print(f"長さ: {len(text)}")  # 文字列の長さを取得
print(f"大文字: {text.upper()}")  # 大文字に変換
print(f"小文字: {text.lower()}")  # 小文字に変換
print(f"置換: {text.replace('Python', 'World')}")  # 文字列の置換
```

### 型変換と型チェック
型変換（キャスト）は、あるデータ型から別のデータ型に値を変換する処理です。Pythonには、安全な型変換のための組み込み関数が用意されています。

```python
# 安全な型変換の例
def safe_convert_to_int(value: str) -> int:
    """
    文字列を整数に安全に変換する
    
    Args:
        value (str): 変換する文字列
    
    Returns:
        int: 変換された整数値
        
    Raises:
        ValueError: 変換できない場合
    """
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"'{value}'を整数に変換できません: {e}")

# 型変換の実践例
examples = ["42", "3.14", "abc", "100"]
for value in examples:
    try:
        result = safe_convert_to_int(value)
        print(f"変換成功: {value} → {result}")
    except ValueError as e:
        print(f"変換失敗: {e}")
```

## 2. データ構造

### 解説
Pythonには、データを効率的に格納・操作するための4つの主要なデータ構造があります。各データ構造には特有の特徴と用途があります。

### リスト（List）
可変で順序付けられた要素の集合です。最も汎用的なデータ構造で、異なる型の要素を含むことができます。

```python
# リストの基本操作と応用例
class ShoppingCart:
    def __init__(self):
        self.items = []
    
    def add_item(self, item: str, quantity: int = 1):
        """商品をカートに追加"""
        for _ in range(quantity):
            self.items.append(item)
    
    def remove_item(self, item: str):
        """商品をカートから削除"""
        if item in self.items:
            self.items.remove(item)
    
    def get_items(self) -> list:
        """カート内の商品を取得"""
        return sorted(self.items)
    
    def get_item_count(self) -> dict:
        """商品ごとの数量を取得"""
        return {item: self.items.count(item) for item in set(self.items)}

# 使用例
cart = ShoppingCart()
cart.add_item("リンゴ", 3)
cart.add_item("バナナ", 2)
print(f"カート内の商品: {cart.get_items()}")
print(f"商品数: {cart.get_item_count()}")
```

### タプル（Tuple）
イミュータブルな（変更不可能な）順序付きの要素の集合です。データの整合性を保証する必要がある場合に使用します。

```python
# タプルの活用例
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
    
    def distance_from_origin(self) -> float:
        """原点からの距離を計算"""
        return (self.x ** 2 + self.y ** 2) ** 0.5

# 座標を使用した例
points = [
    Point(3, 4),
    Point(1, 2),
    Point(5, 12)
]

for point in points:
    distance = point.distance_from_origin()
    print(f"点({point.x}, {point.y})の原点からの距離: {distance:.2f}")
```

### 辞書（Dictionary）
キーと値のペアを格納する連想配列です。高速なルックアップが必要な場合に適しています。

```python
# 辞書の実践的な使用例
class UserDatabase:
    def __init__(self):
        self.users = {}
    
    def add_user(self, user_id: int, name: str, age: int):
        """ユーザーを追加"""
        self.users[user_id] = {
            "name": name,
            "age": age,
            "created_at": datetime.now()
        }
    
    def get_user(self, user_id: int) -> Optional[dict]:
        """ユーザー情報を取得"""
        return self.users.get(user_id)
    
    def update_user(self, user_id: int, **kwargs):
        """ユーザー情報を更新"""
        if user_id in self.users:
            self.users[user_id].update(kwargs)
            return True
        return False

# 使用例
db = UserDatabase()
db.add_user(1, "Alice", 30)
db.add_user(2, "Bob", 25)
print(f"ユーザー1: {db.get_user(1)}")
db.update_user(1, age=31)
```

### セット（Set）
重複のない要素の集合です。要素の一意性を保証する必要がある場合や、集合演算を行う場合に使用します。

```python
# セットの実践的な使用例
class TagManager:
    def __init__(self):
        self.tags = set()
    
    def add_tags(self, *tags: str):
        """タグを追加"""
        self.tags.update(tag.lower() for tag in tags)
    
    def remove_tags(self, *tags: str):
        """タグを削除"""
        for tag in tags:
            self.tags.discard(tag.lower())
    
    def has_tag(self, tag: str) -> bool:
        """タグの存在確認"""
        return tag.lower() in self.tags
    
    def get_tags(self) -> set:
        """全タグを取得"""
        return self.tags.copy()

# 使用例
manager = TagManager()
manager.add_tags("Python", "Programming", "Tutorial")
print(f"全タグ: {manager.get_tags()}")
print(f"'python'タグの存在: {manager.has_tag('python')}")
```

## 3. 制御構文

### 解説
制御構文は、プログラムの実行フローを制御するための基本的な構文です。条件分岐とループが主要な制御構文となります。

### 条件分岐
条件に基づいて異なる処理を実行する際に使用します。

```python
# 条件分岐の実践的な例
class AgeValidator:
    def __init__(self, age: int):
        self.age = age
    
    def get_category(self) -> str:
        """年齢カテゴリを判定"""
        if self.age < 0:
            raise ValueError("年齢は0以上である必要があります")
        elif self.age < 13:
            return "子供"
        elif self.age < 20:
            return "青少年"
        elif self.age < 65:
            return "大人"
        else:
            return "シニア"
    
    def can_drink(self) -> bool:
        """飲酒可能かどうかを判定"""
        return self.age >= 20

# 使用例
validator = AgeValidator(25)
print(f"カテゴリ: {validator.get_category()}")
print(f"飲酒可能: {validator.can_drink()}")
```

### ループ処理
同じ処理を繰り返し実行する際に使用します。Pythonには、`for`文と`while`文の2種類のループ構文があります。

```python
# ループの実践的な例
class FibonacciGenerator:
    def __init__(self, max_count: int):
        self.max_count = max_count
    
    def generate(self) -> List[int]:
        """フィボナッチ数列を生成"""
        sequence = [0, 1]
        while len(sequence) < self.max_count:
            sequence.append(sequence[-1] + sequence[-2])
        return sequence
    
    def generate_until(self, max_value: int) -> List[int]:
        """指定値以下のフィボナッチ数列を生成"""
        sequence = [0, 1]
        while True:
            next_value = sequence[-1] + sequence[-2]
            if next_value > max_value:
                break
            sequence.append(next_value)
        return sequence

# 使用例
generator = FibonacciGenerator(10)
print(f"最初の10個: {generator.generate()}")
print(f"100以下の数列: {generator.generate_until(100)}")
```

## 4. 関数とラムダ

### 解説
関数は、コードの再利用性を高め、プログラムを構造化するための基本的な構成要素です。Pythonでは、関数も一級オブジェクトとして扱われ、変数に代入したり、他の関数の引数として渡したりすることができます。

### 関数の種類と特徴

#### 通常の関数
```python
# 関数定義の実践例
from typing import List, Callable

def calculate_total(numbers: List[float],
                   transform: Callable[[float], float] = lambda x: x) -> float:
    """
    数値リストの合計を計算する
    
    Args:
        numbers: 数値のリスト
        transform: 各数値に適用する変換関数（オプション）
    
    Returns:
        変換後の数値の合計
    """
    return sum(transform(n) for n in numbers)

# 使用例
numbers = [1, 2, 3, 4, 5]
print(f"合計: {calculate_total(numbers)}")
print(f"2乗の合計: {calculate_total(numbers, lambda x: x**2)}")
```

#### デコレータ
関数やクラスの動作を修飾するための機能です。

```python
# デコレータの実践例
from functools import wraps
import time

def timing_decorator(func):
    """関数の実行時間を計測するデコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__}の実行時間: {end_time - start_time:.4f}秒")
        return result
    return wrapper

@timing_decorator
def slow_function(n: int):
    """時間のかかる処理をシミュレート"""
    time.sleep(n)
    return n ** 2

# 使用例
result = slow_function(2)
print(f"結果: {result}")
```

### ジェネレータ関数
メモリ効率の良い反復処理を実現するための機能です。

```python
# ジェネレータの実践例
def prime_generator(max_number: int):
    """素数を生成するジェネレータ"""
    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return False
        return True
    
    for n in range(2, max_number + 1):
        if is_prime(n):
            yield n

# 使用例
primes = prime_generator(100)
print("100以下の素数:")
for prime in primes:
    print(prime, end=" ")
print()
```

## 5. クラスとオブジェクト指向

### 解説
オブジェクト指向プログラミングは、データと振る舞いをカプセル化し、再利用可能なコードを作成するためのパラダイムです。Pythonは、完全なオブジェクト指向言語です。

### クラスの基本概念
- **カプセル化**: データと操作を1つのユニットにまとめる
- **継承**: 既存のクラスの機能を拡張する
- **ポリモーフィズム**: 同じインターフェースで異なる実装を提供する

```python
class Vehicle(ABC):
    """乗り物の抽象基底クラス"""
    def __init__(self, model: str, year: int):
        self._model = model  # プロテクテッド属性
        self._year = year
        self._speed = 0  # 現在の速度
    
    @property
    def model(self) -> str:
        """モデル名を取得"""
        return self._model
    
    @property
    def year(self) -> int:
        """製造年を取得"""
        return self._year
    
    @property
    def speed(self) -> float:
        """現在の速度を取得"""
        return self._speed
    
    @abstractmethod
    def accelerate(self, speed_increase: float):
        """速度を上げる（抽象メソッド）"""
        pass
    
    @abstractmethod
    def brake(self, speed_decrease: float):
        """速度を下げる（抽象メソッド）"""
        pass

class Car(Vehicle):
    """車クラス"""
    def __init__(self, model: str, year: int, max_speed: float = 180.0):
        super().__init__(model, year)
        self._max_speed = max_speed
    
    def accelerate(self, speed_increase: float):
        """速度を上げる"""
        new_speed = self._speed + speed_increase
        self._speed = min(new_speed, self._max_speed)
    
    def brake(self, speed_decrease: float):
        """速度を下げる"""
        new_speed = self._speed - speed_decrease
        self._speed = max(new_speed, 0)
    
    def honk(self):
        """クラクションを鳴らす"""
        return "ビビビー！"

class Bicycle(Vehicle):
    """自転車クラス"""
    def __init__(self, model: str, year: int):
        super().__init__(model, year)
        self._max_speed = 40.0
    
    def accelerate(self, speed_increase: float):
        """速度を上げる（人力による制限あり）"""
        new_speed = self._speed + (speed_increase * 0.5)  # 人力による制限
        self._speed = min(new_speed, self._max_speed)
    
    def brake(self, speed_decrease: float):
        """速度を下げる"""
        new_speed = self._speed - speed_decrease
        self._speed = max(new_speed, 0)
    
    def ring_bell(self):
        """ベルを鳴らす"""
        return "チリーン！"

# 使用例
def test_vehicles():
    # 車のテスト
    car = Car("Toyota Camry", 2024)
    car.accelerate(50)
    print(f"車の速度: {car.speed}km/h")
    car.brake(20)
    print(f"ブレーキ後の速度: {car.speed}km/h")
    print(f"クラクション: {car.honk()}")
    
    # 自転車のテスト
    bike = Bicycle("Giant", 2023)
    bike.accelerate(20)
    print(f"自転車の速度: {bike.speed}km/h")
    print(f"ベル: {bike.ring_bell()}")

# テストの実行
test_vehicles()
```

### クラスの高度な機能

#### データクラス
Pythonの`dataclass`デコレータを使用すると、データを格納するためのクラスを簡潔に定義できます。

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Product:
    """商品を表すデータクラス"""
    id: int
    name: str
    price: float
    created_at: datetime = field(default_factory=datetime.now)
    
    def calculate_tax(self, tax_rate: float = 0.1) -> float:
        """税込価格を計算"""
        return self.price * (1 + tax_rate)

# データクラスの使用例
product = Product(1, "ノートPC", 89800)
print(f"商品: {product.name}")
print(f"税込価格: {product.calculate_tax():.0f}円")
```

#### Mixinクラス
継承を通じて既存のクラスに機能を追加するためのクラスです。

```python
class LoggerMixin:
    """ログ出力機能を提供するMixin"""
    def log(self, message: str):
        print(f"[{datetime.now()}] {self.__class__.__name__}: {message}")

class SerializableMixin:
    """シリアライズ機能を提供するMixin"""
    def to_dict(self) -> dict:
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_')
        }

class SmartProduct(Product, LoggerMixin, SerializableMixin):
    """Mixinを使用した拡張商品クラス"""
    def __init__(self, id: int, name: str, price: float):
        super().__init__(id, name, price)
        self.log(f"商品 {name} を作成しました")
    
    def update_price(self, new_price: float):
        """価格を更新"""
        self.log(f"価格を {self.price} から {new_price} に更新します")
        self.price = new_price

# Mixinの使用例
smart_product = SmartProduct(1, "スマートウォッチ", 29800)
print(f"商品データ: {smart_product.to_dict()}")
smart_product.update_price(27800)
```

## 6. 例外処理

### 解説
例外処理は、プログラムの実行中に発生する可能性のあるエラーを適切に処理するための機能です。Pythonでは、`try-except`文を使用して例外を捕捉し、処理することができます。

### 基本的な例外処理パターン

```python
class BankAccount:
    """銀行口座を表すクラス"""
    def __init__(self, account_number: str, balance: float = 0):
        self.account_number = account_number
        self._balance = balance
    
    class InsufficientFundsError(Exception):
        """残高不足を表す独自の例外"""
        pass
    
    def deposit(self, amount: float):
        """入金処理"""
        if amount <= 0:
            raise ValueError("入金額は正の数である必要があります")
        self._balance += amount
    
    def withdraw(self, amount: float):
        """出金処理"""
        if amount <= 0:
            raise ValueError("出金額は正の数である必要があります")
        if amount > self._balance:
            raise self.InsufficientFundsError(
                f"残高不足です（残高: {self._balance}, 出金要求: {amount}）"
            )
        self._balance -= amount
    
    @property
    def balance(self) -> float:
        """現在の残高を取得"""
        return self._balance

def process_transaction(account: BankAccount, transaction_type: str, amount: float):
    """取引を実行する"""
    try:
        if transaction_type == "deposit":
            account.deposit(amount)
        elif transaction_type == "withdraw":
            account.withdraw(amount)
        else:
            raise ValueError(f"不正な取引種別: {transaction_type}")
        
    except ValueError as e:
        print(f"エラー: {e}")
    except BankAccount.InsufficientFundsError as e:
        print(f"残高不足エラー: {e}")
    except Exception as e:
        print(f"予期せぬエラー: {e}")
    else:
        print("取引が正常に完了しました")
    finally:
        print(f"現在の残高: {account.balance}円")

# 例外処理の使用例
account = BankAccount("1234-5678", 10000)
process_transaction(account, "deposit", 5000)  # 正常な入金
process_transaction(account, "withdraw", 20000)  # 残高不足
process_transaction(account, "transfer", 1000)  # 不正な取引種別
```

このコードは、実際のアプリケーション開発で必要となる主要な概念と実装パターンをカバーしています。特に以下の点に注目してください：

- 抽象基底クラスとインターフェースの使用
- カプセル化とプロパティの適切な使用
- Mixinによる機能の追加
- カスタム例外の定義と例外処理
- 型ヒントの活用
- ドキュメンテーションの重要性

これらの実装例は、実際のプロジェクトでも応用可能な実践的なパターンを示しています。必要に応じて、さらに特定の部分の詳細な説明や追加の例を提供できます。
