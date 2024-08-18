### Pythonの基本知識

以下にPythonの基本知識をマークダウン形式で記載します：

# Python基本知識

## 1. 変数と型

```python
# 整数
x = 5

# 浮動小数点
y = 3.14

# 文字列
name = "Python"

# ブール値
is_true = True
```

## 2. 基本的なデータ構造

### リスト
```python
fruits = ["apple", "banana", "cherry"]
```

### タプル
```python
coordinates = (10, 20)
```

### 辞書
```python
person = {"name": "Alice", "age": 30}
```

### セット
```python
unique_numbers = {1, 2, 3, 4, 5}
```

## 3. 条件文

```python
if x > 0:
    print("正の数")
elif x < 0:
    print("負の数")
else:
    print("ゼロ")
```

## 4. ループ

### for文
```python
for i in range(5):
    print(i)
```

### while文
```python
count = 0
while count < 5:
    print(count)
    count += 1
```

## 5. 関数

```python
def greet(name):
    return f"こんにちは、{name}さん！"

message = greet("太郎")
print(message)
```

## 6. クラス

```python
class Dog:
    def __init__(self, name):
        self.name = name
    
    def bark(self):
        return f"{self.name}が吠えました！"

my_dog = Dog("ポチ")
print(my_dog.bark())
```
はい、SQLクエリの導入と関数実行方法についても追加で説明いたします。

## 7. SQLクエリの導入

Pythonでは、データベース操作のためにSQLiteやMySQL、PostgreSQLなどのデータベースと連携することができます。ここでは、SQLiteを使用した例を示します。

```python
import sqlite3

# データベースに接続
conn = sqlite3.connect('example.db')
cursor = conn.cursor()

# テーブルの作成
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER
    )
''')

# データの挿入
cursor.execute("INSERT INTO users (name, age) VALUES (?, ?)", ("Alice", 30))

# データの取得
cursor.execute("SELECT * FROM users WHERE age > ?", (25,))
results = cursor.fetchall()

for row in results:
    print(row)

# 変更を保存し、接続を閉じる
conn.commit()
conn.close()
```

このコードは、SQLiteデータベースに接続し、テーブルを作成し、データを挿入し、そしてクエリを実行してデータを取得します。

## 8. 関数の実行方法

Pythonでは、関数を定義した後、さまざまな方法で実行することができます。

### 基本的な関数の実行

```python
def greet(name):
    return f"こんにちは、{name}さん！"

# 関数の実行と結果の表示
print(greet("太郎"))
```

### 引数を使った関数の実行

```python
def calculate_area(length, width):
    return length * width

# 位置引数を使用
area1 = calculate_area(5, 3)
print(f"面積1: {area1}")

# キーワード引数を使用
area2 = calculate_area(width=4, length=6)
print(f"面積2: {area2}")
```

### デフォルト引数を持つ関数

```python
def power(base, exponent=2):
    return base ** exponent

# デフォルト引数を使用
result1 = power(3)  # 3の2乗
print(f"結果1: {result1}")

# デフォルト引数を上書き
result2 = power(3, 3)  # 3の3乗
print(f"結果2: {result2}")
```

### 可変長引数を持つ関数

```python
def sum_all(*args):
    return sum(args)

# 複数の引数を渡す
result = sum_all(1, 2, 3, 4, 5)
print(f"合計: {result}")
```

### ラムダ関数（無名関数）

```python
# ラムダ関数の定義と実行
square = lambda x: x ** 2
print(f"3の2乗: {square(3)}")

# リスト内の要素に対してラムダ関数を適用
numbers = [1, 2, 3, 4, 5]
squared_numbers = list(map(lambda x: x ** 2, numbers))
print(f"2乗されたリスト: {squared_numbers}")
```

これらの例は、Pythonにおける関数の定義と実行の基本的な方法を示しています。関数は、コードの再利用性を高め、プログラムの構造を整理するのに役立ちます。

