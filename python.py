import random

def bite(probability=0.5):
    """噛む確率に基づいて噛まれるかどうかを判定"""
    if not 0 <= probability <= 1:
        raise ValueError("確率は0から1の間でなければなりません。")
    return random.random() < probability

def main():
    try:
        # 噛まれるかどうかを判定
        if bite():
            print("パイソンに噛まれました！")
        else:
            print("パイソンに噛まれませんでした。")
    except ValueError as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    main()
