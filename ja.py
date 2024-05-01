import random

rock_paper_scissors = ['グー', 'チョキ', 'パー']

print('じゃんけんしましょう')
print('番号を入力してね')
print('1番・グー　2番・チョキ　3番・パー')

number = input('あなたの手は？　')

if number == '1':
    user = 'グー'
elif number == '2':
    user = 'チョキ'
elif number == '3':
    user = 'パー'
else:
    print('無効な入力です。プログラムを終了します。')
    exit()

cpu = random.choice(rock_paper_scissors)

print(f'あなたは{user}。向こうは{cpu}。')

if user == cpu:
    print('あいこ！')
elif (user == 'グー' and cpu == 'チョキ') or (user == 'チョキ' and cpu == 'パー') or (user == 'パー' and cpu == 'グー'):
    print('あなたの勝ち！')
else:
    print('あなたの負け！')