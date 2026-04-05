"""
不良ヤンキーキャラクター実装
ヤンキー: 日本の不良文化を体現するキャラクター
"""

import random
import time


class Yankee:
    """不良ヤンキーキャラクタークラス"""

    GREETINGS = [
        "よォ、おまえか。",
        "あァ？なんか用か？",
        "チッ、うるせーな。",
        "おい、こっち来い。",
        "なめんじゃねーぞ。",
    ]

    THREATS = [
        "表出ろや、コラァ！",
        "ぶっとばすぞ、テメェ！",
        "いい度胸じゃねーか。",
        "覚悟しろよ、おい。",
        "やんのかコラ！",
    ]

    COOL_LINES = [
        "俺はな、曲がったことが嫌いなんだよ。",
        "義理と人情、それだけだ。",
        "仲間を傷つけるやつは許さねー。",
        "男なら一本筋通せや。",
        "弱いもんいじめは、俺が許さん。",
    ]

    REACTIONS = {
        "怒": ["ああ？！", "テメェ！！", "やんのかコラ！", "ぶっとばすぞ！"],
        "驚": ["なっ…！", "マジか！", "うそだろ…", "ちょ、待て待て！"],
        "嬉": ["……そーか。", "まあ、悪くねーな。", "チッ、照れんじゃねーよ。", "……ありがとよ。"],
        "悲": ["うるさい黙れ。", "…関係ねーだろ。", "……チッ。", "見んじゃねー。"],
    }

    POMPADOUR = r"""
      ___
    /|   |\
   / |   | \
  /  |   |  \
 |   \___/   |
 |   (O O)   |
 |    \=/    |
  \   |||   /
   \  |||  /
    \_|||_/
      |||
  ~~~~|||~~~~
      |_|
"""

    def __init__(self, name: str = "タケシ", territory: str = "東側"):
        self.name = name
        self.territory = territory
        self.hp = 100
        self.respect = 0  # 仁義ポイント
        self.is_angry = False

    def __repr__(self) -> str:
        return f"<Yankee name={self.name!r} territory={self.territory!r} respect={self.respect}>"

    def show_face(self) -> None:
        """ヤンキーの顔を表示"""
        print(self.POMPADOUR)
        print(f"  名前: {self.name}")
        print(f"  縄張り: {self.territory}")
        print(f"  仁義: {self.respect} pt")
        print(f"  HP: {'█' * (self.hp // 10)}{'░' * (10 - self.hp // 10)} {self.hp}/100")

    def greet(self) -> str:
        """あいさつ（ヤンキー風）"""
        line = random.choice(self.GREETINGS)
        print(f"{self.name}: 「{line}」")
        return line

    def threaten(self, target: str = "おまえ") -> str:
        """脅す"""
        self.is_angry = True
        line = random.choice(self.THREATS)
        print(f"{self.name}: 「{line} {target}！」")
        return line

    def say_cool_thing(self) -> str:
        """かっこいいセリフを言う"""
        line = random.choice(self.COOL_LINES)
        print(f"{self.name}: 「{line}」")
        self.respect += 10
        return line

    def react(self, emotion: str) -> str:
        """感情に反応する"""
        if emotion not in self.REACTIONS:
            emotion = random.choice(list(self.REACTIONS.keys()))
        line = random.choice(self.REACTIONS[emotion])
        print(f"{self.name}: 「{line}」")
        return line

    def fight(self, opponent: "Yankee") -> "Yankee":
        """喧嘩する"""
        print(f"\n{'='*40}")
        print(f"  ★ {self.name} VS {opponent.name} ★")
        print(f"{'='*40}")

        round_num = 1
        while self.hp > 0 and opponent.hp > 0:
            print(f"\n--- ラウンド {round_num} ---")
            time.sleep(0.3)

            # 自分の攻撃
            damage = random.randint(10, 30)
            opponent.hp = max(0, opponent.hp - damage)
            print(f"{self.name} の攻撃！ → {opponent.name} に {damage} ダメージ！")
            print(f"  {opponent.name} HP: {opponent.hp}/100")

            if opponent.hp <= 0:
                break

            time.sleep(0.3)

            # 相手の攻撃
            damage = random.randint(10, 30)
            self.hp = max(0, self.hp - damage)
            print(f"{opponent.name} の反撃！ → {self.name} に {damage} ダメージ！")
            print(f"  {self.name} HP: {self.hp}/100")

            round_num += 1
            time.sleep(0.3)

        winner = self if self.hp > 0 else opponent
        loser = opponent if winner is self else self

        print(f"\n{'='*40}")
        print(f"  勝者: {winner.name}！！")
        print(f"{'='*40}")
        print(f"{winner.name}: 「立てよ、まだ終わってねーだろ。」")
        winner.respect += 50
        loser.hp = 1  # 死なせない（仁義）
        return winner

    def show_jingi(self) -> None:
        """仁義を切る（正式なあいさつ）"""
        print(f"\n{self.name}: 「手前、{self.territory}を縄張りにしております、")
        time.sleep(0.5)
        print(f"         {self.name} と申します。以後、お見知りおきを。」")
        self.respect += 20

    def status(self) -> dict:
        """ステータスを返す"""
        return {
            "name": self.name,
            "territory": self.territory,
            "hp": self.hp,
            "respect": self.respect,
            "is_angry": self.is_angry,
        }


class YankeeGroup:
    """ヤンキーグループ（チーム）"""

    def __init__(self, group_name: str):
        self.group_name = group_name
        self.members: list[Yankee] = []
        self.boss: Yankee | None = None

    def add_member(self, yankee: Yankee) -> None:
        self.members.append(yankee)
        if self.boss is None:
            self.boss = yankee
            print(f"{yankee.name} が {self.group_name} のボスになった！")
        else:
            print(f"{yankee.name} が {self.group_name} に加入した！")

    def roll_call(self) -> None:
        """点呼"""
        print(f"\n【{self.group_name} 点呼！】")
        for i, member in enumerate(self.members, 1):
            role = "ボス" if member is self.boss else "メンバー"
            print(f"  {i}. {member.name} ({role}) - 仁義 {member.respect}pt")

    def total_respect(self) -> int:
        return sum(m.respect for m in self.members)


def main():
    print("=" * 50)
    print("  不良ヤンキーシミュレーター 🎮")
    print("=" * 50)

    # キャラクター作成
    takeshi = Yankee("タケシ", "東側")
    ryu = Yankee("リュウ", "西側")

    # 顔を見せる
    takeshi.show_face()

    print("\n--- 仁義を切る ---")
    takeshi.show_jingi()

    print("\n--- あいさつ ---")
    takeshi.greet()

    print("\n--- かっこいいセリフ ---")
    takeshi.say_cool_thing()

    print("\n--- 感情リアクション ---")
    takeshi.react("怒")
    takeshi.react("嬉")

    print("\n--- 喧嘩勃発！ ---")
    winner = takeshi.fight(ryu)

    print(f"\n最終ステータス: {winner.status()}")

    # グループ
    print("\n--- グループ編成 ---")
    group = YankeeGroup("東風連合")
    group.add_member(takeshi)
    group.add_member(Yankee("ケンジ", "東側"))
    group.add_member(Yankee("マサル", "東側"))
    group.roll_call()
    print(f"\n総仁義ポイント: {group.total_respect()}pt")


if __name__ == "__main__":
    main()
