import random


fortunes = ['大吉', '吉', '凶', '大凶']
fortune = random.choice(fortunes)
print(fortune)


##追加バージョン

import random
import time


fortunes = ['大吉', '吉', '凶', '大凶']
fortune = random.choice(fortunes)

print('おみくじを引きます・・・')
time.sleep(1)
for i in range(3):
    if i % 2 == 0:
        print('ガサッ')
    else:
        print('ゴソッ')
    time.sleep(1)
print('＿人人人人人人人人人＿')
print(f'＞{fortune.center(16)}＜')
print('￣Y^Y^Y^Y^Y^Y^Y^Y^Y￣')
