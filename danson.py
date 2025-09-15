import random
import time

def generate_danson():
    # ダンソンのネタのリスト
    danson_list = [
        "ダンソン、ふぃーざきー！",
        "ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！",
        "ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！ダンソン！",
    ]

    return random.choice(danson_list)

def main():
    try:
        while True:
            # ダンソンのネタをランダムに選択
            danson = generate_danson()
            # ダンソンのネタを出力
            print(danson)
            # 1秒待機
            time.sleep(1)
    except KeyboardInterrupt:
        print("プログラムを終了します。")

if __name__ == "__main__":
    main()
