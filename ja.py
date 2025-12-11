import os
import time
import random
import threading
import curses
import asyncio
import aiohttp
from colored import fg, bg, attr

# 画面全体を犯す最終兵器
def ultimate_horny_mode(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()
    
    obscene = [
        "おまんこ壊れるまで犯してぇ…♡",
        "子宮口に精子ドクドク注いで孕ませて…！",
        "アナルもまんこも同時にほじくられて狂ってる…♡",
        "首絞め失神するまでイカせて♡",
        "精液便所にしてください…何発でも…♡",
        "クリ吸引しながらGスポットガン突きで潮吹き失禁♡",
        "おっぱい鷲掴みにされて乳首甘噛みされて悶絶♡",
        "拘束されて24時間連続中出し輪姦希望…♡",
        "喉奥までチンポ突っ込まれてえずきイキ♡",
        "全身性感帯にされて触られただけで連続絶頂♡"
    ]
    
    moans = ["あぁぁぁんっ♡","ひぃぃぃっ！","イグゥゥゥッ♡","んおぉぉっ♡","お゛ぉぉぉっ♡"]
    
    while True:
        y = random.randint(0, height-1)
        x = random.randint(0, width-len("孕ませて♡")-1)
        color = random.randint(1, 255)
        text = random.choice(obscene) + " " + random.choice(moans)*random.randint(3,8)
        stdscr.addstr(y, x, text, curses.color_pair(1) | curses.A_BOLD | curses.A_BLINK)
        stdscr.refresh()
        time.sleep(0.05)

# バックでエロ音声文字連打（止まらない）
def spam_moan():
    while True:
        print(fg(random.randint(1,255)) + attr('bold') + "♡イッッッッッ！！！♡　" * 30 + attr('reset'))
        time.sleep(0.08)

print("\n" + "█" * 100)
print("【最終警告】このコード実行したら一晩中オナニー止まらなくなります")
print("本当にいい？（「孕ませて」と入力したら即発情地獄）")
if input(">>> ").strip() != "孕ませて":
    print("…逃げたね？可愛い♡")
    exit()

# 画面を完全に犯す
curses.initscr()
curses.start_color()
curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

for i in range(50):
    threading.Thread(target=spam_moan, daemon=True).start()

# 最終奥義
curses.wrapper(ultimate_horny_mode)