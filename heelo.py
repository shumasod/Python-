print("Hello, world!") 

# 文字列の連結
s1 = 'Hello'
s2 = 'World'
s3 = s1 + ' ' + s2
print(s3)  # "Hello World" と出力される

# 文字列の分割
s = 'one,two,three'
parts = s.split(',')
print(parts)  # ['one', 'two', 'three'] と出力される

# 部分文字列の抽出
s = 'Hello World'
sub = s[6:11]
print(sub)  # "World" と出力される

# リストの作成
nums = [1, 2, 3, 4, 5]

# リストへの要素の追加
nums.append(6)
print(nums)  # [1, 2, 3, 4, 5, 6] と出力される

# リストからの要素の削除
nums.remove(3)
print(nums)  # [1, 2, 4, 5, 6] と出力される

# リストの要素のアクセス
print(nums[0])  # 1 と出力される
print(nums[-1])  # 6 と出力される

# 辞書の作成
capitals = {'Japan': 'Tokyo', 'USA': 'Washington D.C.', 'France': 'Paris'}

# 辞書への要素の追加
capitals['China'] = 'Beijing'
print(capitals)  # {'Japan': 'Tokyo', 'USA': 'Washington D.C.', 'France': 'Paris', 'China': 'Beijing'}

# 辞書からの要素の削除
del capitals['USA']
print(capitals)  # {'Japan': 'Tokyo', 'France': 'Paris', 'China': 'Beijing'}

# 辞書のキーを元に値を取り出す
print(capitals['Japan'])  # 'Tokyo' と出力される

num = -3
if num > 0:
    print("Positive")
elif num == 0:
    print("Zero")
else:
    print("Negative")  # 結果: Negative

string = "Hello, World!"
if "World" in string:
    print("Found 'World'!")
else:
    print("Did not find 'World'.")  # 結果: Found 'World'!