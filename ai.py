import random
import time
import os
import threading
from colorama import init, Fore, Back, Style

init(autoreset=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def squirt_effect(intensity=100):
    lines = [
        "　　♡　　あぁんっ！　　♡",
        "　　　いくっ…いくいくいくぅぅぅっ！！",
        "　　　　　　ピュッ！ピュルルルルルルル！！",
        "　　ﾋﾟﾁｬｯ！　ﾋﾟｭﾙﾙﾙﾙﾙﾙ！！　　ﾋﾟﾁｬﾋﾟﾁｬ！！",
        "　　　びちゃぁぁぁぁぁぁぁぁぁ！！！",
        "　　イッッッッッッッッッッッッッッ！！！！"
    ]
    
    colors = [Fore.MAGENTA, Fore.PINK, Fore.LIGHTMAGENTA_EX, Fore.LIGHTRED_EX]
    
    for _ in range(intensity // 10):
        clear_screen()
        for i, line in enumerate(lines):
            color = random.choice(colors)
            delay = random.uniform(0.02, 0.08)
            print(" " * random.randint(0, 30) + color + Style.BRIGHT + line)
            time.sleep(delay)
        
        print("\n" * 3)
        print(" " * 20 + Back.MAGENTA + Fore.WHITE + " 大量潮吹き中 " + Style.RESET_ALL + " x" + str(random.randint(50, 200)) + "ml")
        print(" " * 20 + "子宮が痙攣してる…♡ もうダメぇ…♡")
        time.sleep(0.15)

def orgasm_countdown(name):
    print(f"\n{Fore.LIGHTMAGENTA_EX}【{name}】の絶頂カウントダウン開始…♡")
    time.sleep(2)
    
    for i in range(10, 0, -1):
        clear_screen()
        print(f"\n\n\n\t\t{Fore.RED}{Style.BRIGHT}あと {i} 秒でイく…♡")
        print(f"\t\t\t{name}の腰が勝手に動いてる…♡")
        time.sleep(1)
    
    # ここから本番の潮吹き
    clear_screen()
    print(f"{Fore.YELLOW}{Style.BRIGHT}\n\t\t{name}がイく瞬間がきたぁぁぁぁっ！！♡♡♡\n")
    time.sleep(1.5)
    
    # 同時多発潮吹きスレッドで超絶頂演出
    threads = []
    for _ in range(8):  # 8方向から潮吹き
        t = threading.Thread(target=squirt_effect, args=(80,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    clear_screen()
    print(f"{Fore.LIGHTCYAN_EX}{Style.BRIGHT}")
    print("　　　♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡")
    print(f"　　　{name}、完全にイキ狂った…♡")
    print("　　　潮吹き量：9999ml超（記録更新）")
    print("　　　連続絶頂回数：47回（まだビクビクしてる…）")
    print("　　　♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡♡")
    print(f"{Style.RESET_ALL}")
    time.sleep(5)

# ============== 実行 ==============
if __name__ == "__main__":
    clear_screen()
    print(f"{Fore.PINK}{Style.BRIGHT}")
    print("　　♡♡♡ 潮吹き絶頂システム v2.0 ♡♡♡")
    print("　　完全にイカせる準備、完了♡\n")
    
    name = input(f"{Fore.LIGHTMAGENTA_EX}　　誰をイカせたい？名前を教えて？ → {Style.RESET_ALL}").strip()
    if not name:
        name = "あなた"
    
    input(f"\n{Fore.RED}　　準備OK？エンターで{name}を本気でイカせます…♡")
    
    orgasm_countdown(name)