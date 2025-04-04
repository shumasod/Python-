

---

# はじめてのPython：やさしい入門ガイド（実践プラクティス付き） 🐍

このガイドは、プログラミング初心者がPythonの基本を学ぶためのステップバイステップの解説書です。コード例や演習問題を通して、実際に手を動かしながら理解を深めましょう。

---

## 目次
1. [プログラミングの基本](#1-プログラミングの基本)
2. [変数とデータの種類](#2-変数とデータの種類)
3. [データ構造の基本](#3-データ構造の基本)
4. [制御構文：条件分岐とループ](#4-制御構文条件分岐とループ)
5. [関数を作ろう](#5-関数を作ろう)
6. [クラスとオブジェクト指向](#6-クラスとオブジェクト指向)
7. [例外処理](#7-例外処理)
8. [実践プラクティス：総合演習](#8-実践プラクティス総合演習)
9. [用語集](#9-用語集)

---

## 1. プログラミングの基本

### 概要
プログラムは、コンピュータに「何をするか」を指示するレシピのようなものです。最初の一歩として、画面にメッセージを表示する簡単なプログラムを作ってみましょう。

### サンプルコード
```python
# はじめてのプログラム
print("こんにちは！")  # 画面に「こんにちは！」と表示される
```

### 🔍 プログラムの基本ルール
- プログラムは上から順に実行されます。
- `#` で始まる行はコメントとして無視されます。
- 文字列は `""` や `''` で囲みます。

### ✍️ 練習問題
1. **名前の表示:** 自分の名前を表示するプログラムを書いてみましょう。  
   例：`print("あなたの名前")`
2. **好きな食べ物:** 好きな食べ物を表示するプログラムを書いてみましょう。

---

## 2. 変数とデータの種類

### 概要
変数は、データを一時的に保存する「箱」です。Pythonでは、データ型が自動で決定されますが、型ヒントを用いることで可読性を向上させることができます。

### サンプルコード
```python
# 変数に値を保存する例
name = "太郎"          # 文字列型（str）
age = 20              # 整数型（int）
height = 170.5        # 浮動小数点型（float）
is_student = True     # 真偽値型（bool）

# 変数を使った文章作成
print(f"{name}さんは{age}歳です")
```

### 📦 主なデータ型
| 種類       | 説明                  | 例             |
|------------|-----------------------|----------------|
| 文字列 (str) | テキストデータ        | "こんにちは"   |
| 整数 (int)  | 整数の数値           | 42             |
| 浮動小数点 (float) | 小数を含む数値  | 3.14           |
| 真偽値 (bool) | True または False   | True, False    |

### ✍️ 練習問題
1. 自分の**名前**、**年齢**、**身長**を変数に保存し、自己紹介文を作成してみましょう。
2. 次のコードを実行して、各変数の型を表示してみましょう。  
   ```python
   print(type(name))
   print(type(age))
   print(type(height))
   print(type(is_student))
   ```

---

## 3. データ構造の基本

Pythonには、データを整理するための便利なデータ構造がいくつかあります。ここでは、リスト、辞書、タプル、セットを解説します。

### 3.1 リスト (List)
順序付けられた変更可能なデータの集合です。

#### サンプルコード
```python
# 買い物リストの例
shopping_list = ["りんご", "バナナ", "オレンジ"]

# リストの操作例
print(shopping_list[0])         # 最初の要素
shopping_list.append("ぶどう")   # 新しい項目を追加
print("リストの長さ:", len(shopping_list))

# リストの各要素を出力
for item in shopping_list:
    print(f"買うもの: {item}")
```

### 3.2 辞書 (Dictionary)
キーと値のペアでデータを管理します。

#### サンプルコード
```python
# 生徒情報を管理する辞書
student = {
    "name": "佐藤花子",
    "age": 15,
    "class": "2年A組",
    "subjects": ["国語", "数学", "英語"]
}

print(f"名前: {student['name']}")
print(f"好きな科目: {student['subjects'][0]}")
```

### 3.3 タプル (Tuple)
変更不可能な順序付きデータの集合です。

#### サンプルコード
```python
# 座標を表すタプルの例
point = (3, 4)
print("x座標:", point[0])
print("y座標:", point[1])
```

### 3.4 セット (Set)
重複しないデータの集合です。

#### サンプルコード
```python
# セットの例
fruits = {"りんご", "バナナ", "オレンジ", "りんご"}
print("ユニークな果物:", fruits)
```

### ✍️ 練習問題
1. **リストの演習:** 好きな食べ物のリストを作成し、新たに「ケーキ」を追加してリスト全体を表示してみましょう。
2. **辞書の演習:** 友だちの名前、年齢、趣味を管理する辞書を作成し、各情報を出力してみましょう。

---

## 4. 制御構文：条件分岐とループ

### 4.1 条件分岐 (if文)
条件に基づいて異なる処理を実行するための文法です。

#### サンプルコード
```python
# 年齢に応じたメッセージ表示
age = 15

if age < 13:
    print("子供料金です")
elif age < 20:
    print("学生料金です")
else:
    print("大人料金です")
```

### 4.2 ループ (for文・while文)
同じ処理を繰り返し実行するための文法です。

#### サンプルコード（for文）
```python
# 1から5までの数字を出力
for i in range(1, 6):
    print(f"{i}回目")
```

#### サンプルコード（while文）
```python
# 1から5までをwhile文で表示
i = 1
while i <= 5:
    print(f"{i}回目")
    i += 1
```

### ✍️ 練習問題
1. **点数判定:** テストの点数（0～100点）を入力し、80点以上なら「合格」、それ以外なら「不合格」と表示するプログラムを作成しましょう。
2. **偶数の表示:** 1から10までの数字をfor文で表示し、偶数の場合は「偶数です」と追加で出力するプログラムを作成しましょう。

---

## 5. 関数を作ろう

### 概要
関数は、よく使う処理をひとまとめにして再利用するための仕組みです。関数を使うことでコードの整理・再利用が容易になります。

### サンプルコード
```python
# 挨拶をする関数の例
def greet(name):
    """名前を受け取って挨拶する関数"""
    return f"こんにちは、{name}さん！"

message = greet("太郎")
print(message)

# 税込価格を計算する関数
def calculate_total(price, tax_rate=0.1):
    """商品の税込価格を計算する関数"""
    return price * (1 + tax_rate)

price = calculate_total(1000)
print(f"税込価格: {price}円")
```

### ✍️ 練習問題
1. **平均計算関数:** 二つまたは複数の数値の平均を計算する関数を作成しましょう。  
   ※ ヒント: 入力としてリストを受け取り、`sum()` と `len()` を利用します。
2. **自己紹介関数:** 名前と年齢を引数にとり、「〇〇さんは〇歳です」と返す関数を作成しましょう。

---

## 6. クラスとオブジェクト指向

### 概要
クラスは、データ（属性）と処理（メソッド）をひとまとめにした設計図です。オブジェクト指向を使うと、複雑なプログラムでも整理されたコードが書けます。

### サンプルコード：ペットクラス
```python
# ペットを表すクラスの例
class Pet:
    def __init__(self, name, animal_type):
        self.name = name
        self.animal_type = animal_type
    
    def make_sound(self):
        """動物ごとの鳴き声を返す"""
        if self.animal_type == "犬":
            return "ワン！"
        elif self.animal_type == "猫":
            return "ニャー！"
        else:
            return "..."

# クラスを使ってインスタンスを作成
my_pet = Pet("ポチ", "犬")
print(f"{my_pet.name}が鳴きました：{my_pet.make_sound()}")
```

### ✍️ 練習問題
1. **本を管理するクラス:** タイトル、著者、価格を属性として持つ `Book` クラスを作成し、各書籍の情報を表示するメソッドを実装しましょう。
2. **生徒クラス:** 名前、年齢、得意科目を属性として持つ `Student` クラスを作成し、自己紹介文を返すメソッドを実装しましょう。

---

## 7. 例外処理

### 概要
プログラム実行中に予期しないエラーが発生した場合、例外処理を使うことでプログラムをクラッシュさせずに適切な対応ができます。

### サンプルコード：銀行口座の例
```python
class BankAccount:
    """銀行口座を表すクラス"""
    def __init__(self, account_number: str, balance: float = 0):
        self.account_number = account_number
        self._balance = balance
    
    class InsufficientFundsError(Exception):
        """残高不足エラー"""
        pass
    
    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("入金額は正の数である必要があります")
        self._balance += amount
    
    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValueError("出金額は正の数である必要があります")
        if amount > self._balance:
            raise self.InsufficientFundsError(
                f"残高不足です（残高: {self._balance}, 出金要求: {amount}）"
            )
        self._balance -= amount
    
    @property
    def balance(self):
        return self._balance

def process_transaction(account, transaction_type, amount):
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
    else:
        print("取引が正常に完了しました")
    finally:
        print(f"現在の残高: {account.balance}円")

# 使用例
account = BankAccount("1234-5678", 10000)
process_transaction(account, "deposit", 5000)
process_transaction(account, "withdraw", 20000)
process_transaction(account, "transfer", 1000)
```

### ✍️ 練習問題
1. ユーザーから数値を入力させ、その入力を整数に変換する際のエラーをキャッチするプログラムを作成しましょう。
2. ファイル操作など、実際に起こり得るエラー処理（`try-except`）のパターンを実装してみましょう。

---

## 8. 実践プラクティス：総合演習

### 課題例：To-Doリスト CLI アプリ
以下の機能を持つ簡単なコマンドライン・アプリケーションを作成してみましょう。

- **タスクの追加:** ユーザーからタスク名を入力させ、リストに追加する
- **タスクの表示:** 現在のタスクリストを番号付きで表示する
- **タスクの削除:** 指定した番号のタスクを削除する
- **終了:** アプリケーションを終了する

※ ヒント  
- リストや辞書を用いてタスクを管理  
- ループと条件分岐でメニューを実装  
- 関数を分割してコードを整理

---

## 9. 用語集

| 用語       | 説明                                            |
|------------|-------------------------------------------------|
| 変数       | データを一時的に保存するための名前付きの「箱」    |
| リスト     | 順序付きの変更可能なデータの集合                 |
| 辞書       | キーと値のペアによるデータの管理方法             |
| タプル     | 順序付きの変更不可能なデータの集合               |
| セット     | 重複しない要素の集合                             |
| 関数       | 再利用可能な処理をまとめたブロック               |
| クラス     | 属性とメソッドをまとめた設計図                   |
| 例外処理   | エラー発生時にプログラムの異常終了を防ぐ処理       |

---

## おわりに

プログラミング学習は、基本を理解した上で実際に手を動かすことが重要です。  
このガイドと実践プラクティスを通して、Pythonの基礎をしっかりと身に付け、さらなる学習やプロジェクトへの第一歩として活用してください。  
わからないことがあれば、積極的に調べたり、質問したりしましょう。😊

Happy Coding!
