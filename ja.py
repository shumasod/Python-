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

cpu = random.choice(rock_paper_scissors)
print(f'あなたは{user}。向こうは{cpu}。')

if user == 'グー':
    if cpu == 'グー':
        print('あいこ！')
    elif cpu == 'チョキ':
        print('あなたの勝ち！')
    elif cpu == 'パー':
        print('あなたの負け！')
elif user == 'チョキ':
    if cpu == 'グー':
        print('あなたの負け')
    elif cpu == 'チョキ':
        print('あいこ！')
    elif cpu == 'パー':
        print('あなたの勝ち！')
elif user == 'パー':
    if cpu == 'グー':
        print('あなたの勝ち！')
    elif cpu == 'チョキ':
        print('あなたの負け！')
    elif cpu == 'パー':
        print('あいこ！')
