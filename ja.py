import random

# じゃんけんの手をリストで定義
rock_paper_scissors = ['グー', 'チョキ', 'パー']

# 戦績を記録する変数
wins = 0
losses = 0
ties = 0

# ゲームを開始
print('じゃんけんを始めましょう！')
print('1番・グー　2番・チョキ　3番・パー')

while True:
    # プレイヤーの手を入力
    number = input('あなたの手を番号で選んでください（終了するには"q"を入力）：')

    if number == 'q':
        break

    if number == '1':
        user = 'グー'
    elif number == '2':
        user = 'チョキ'
    elif number == '3':
        user = 'パー'
    else:
        print('無効な入力です。もう一度試してください。')
        continue

    # CPUの手をランダムに選択
    cpu = random.choice(rock_paper_scissors)

    print(f'あなたは{user}、CPUは{cpu}です。')

    # 勝敗を判断
    if user == cpu:
        print('あいこ！')
        ties += 1
    elif (user == 'グー' and cpu == 'チョキ') or (user == 'チョキ' and cpu == 'パー') or (user == 'パー' and cpu == 'グー'):
        print('あなたの勝ち！')
        wins += 1
    else:
        print('あなたの負け！')
        losses += 1

    # 現在の戦績を表示
    print(f'現在の戦績: {wins}勝, {losses}敗, {ties}引き分け\n')

    # 特定の条件でメッセージを表示
    if ties > 0 and ties % 3 == 0:
        print('3連続あいこ！これはなかなか珍しいことですね！')

# ゲーム終了時の総合結果を表示
print(f'ゲーム終了！最終戦績: {wins}勝, {losses}敗, {ties}引き分け')
