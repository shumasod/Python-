"""
不良ヤンキーキャラクター実装
ヤンキー: 日本の不良文化を体現するキャラクター
"""

import random
import time


# ─── ランク定義 ───────────────────────────────────────────
RANK_THRESHOLDS = [
    (200, "伝説", "👑"),
    (150, "最強", "🔥"),
    (100, "番長",  "⚡"),
    (60,  "幹部",  "★"),
    (30,  "一般",  "・"),
    (0,   "チンピラ", "…"),
]


def get_rank(respect: int) -> tuple[str, str]:
    for threshold, title, icon in RANK_THRESHOLDS:
        if respect >= threshold:
            return title, icon
    return "チンピラ", "…"


# ─── Yankee クラス ────────────────────────────────────────
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
        "義理と人情、それだけだけだ。",
        "仲間を傷つけるやつは許さねー。",
        "男なら一本筋通せや。",
        "弱いもんいじめは、俺が許さん。",
        "負けても、魂まで負けちゃいねーぞ。",
        "俺が守る。それだけだ。",
    ]

    REACTIONS = {
        "怒": ["ああ？！", "テメェ！！", "やんのかコラ！", "ぶっとばすぞ！"],
        "驚": ["なっ…！", "マジか！", "うそだろ…", "ちょ、待て待て！"],
        "嬉": ["……そーか。", "まあ、悪くねーな。", "チッ、照れんじゃねーよ。", "……ありがとよ。"],
        "悲": ["うるさい黙れ。", "…関係ねーだろ。", "……チッ。", "見んじゃねー。"],
    }

    # 必殺技: (名前, ダメージ倍率, 発動確率, 台詞)
    SPECIAL_MOVES = [
        ("魂の一撃",     2.5, 0.15, "これが俺の全てだ！！"),
        ("東側正拳突き", 2.0, 0.20, "受けてみろやァ！！"),
        ("義理砕き",     1.8, 0.25, "俺の義理、舐めんじゃねー！"),
        ("仁義の鉄拳",   1.5, 0.30, "仁義、見せてやるよ！"),
    ]

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
        self.max_hp = 100
        self.respect = 0  # 仁義ポイント
        self.is_angry = False
        self.win_streak = 0  # 連勝数
        self.rivals: list["Yankee"] = []

    def __repr__(self) -> str:
        rank, icon = get_rank(self.respect)
        return f"<Yankee {icon}{rank} name={self.name!r} territory={self.territory!r} respect={self.respect}>"

    # ── 表示 ──────────────────────────────────────────────
    def show_face(self) -> None:
        """ヤンキーの顔を表示"""
        rank, icon = get_rank(self.respect)
        print(self.POMPADOUR)
        print(f"  名前   : {self.name}")
        print(f"  縄張り : {self.territory}")
        print(f"  ランク : {icon} {rank}")
        print(f"  仁義   : {self.respect} pt")
        filled = self.hp * 10 // self.max_hp
        print(f"  HP     : {'█' * filled}{'░' * (10 - filled)} {self.hp}/{self.max_hp}")
        print(f"  連勝   : {self.win_streak} 連勝")
        if self.rivals:
            print(f"  ライバル: {', '.join(r.name for r in self.rivals)}")

    # ── セリフ系 ──────────────────────────────────────────
    def greet(self) -> str:
        line = random.choice(self.GREETINGS)
        print(f"{self.name}: 「{line}」")
        return line

    def threaten(self, target: str = "おまえ") -> str:
        self.is_angry = True
        line = random.choice(self.THREATS)
        print(f"{self.name}: 「{line} {target}！」")
        return line

    def say_cool_thing(self) -> str:
        line = random.choice(self.COOL_LINES)
        print(f"{self.name}: 「{line}」")
        self.respect += 10
        return line

    def react(self, emotion: str) -> str:
        if emotion not in self.REACTIONS:
            emotion = random.choice(list(self.REACTIONS.keys()))
        line = random.choice(self.REACTIONS[emotion])
        print(f"{self.name}: 「{line}」")
        return line

    def show_jingi(self) -> None:
        """仁義を切る（正式なあいさつ）"""
        print(f"\n{self.name}: 「手前、{self.territory}を縄張りにしております、")
        time.sleep(0.4)
        print(f"         {self.name} と申します。以後、お見知りおきを。」")
        self.respect += 20

    # ── 戦闘 ──────────────────────────────────────────────
    def _try_special(self, base_damage: int) -> tuple[int, str | None]:
        """必殺技判定。(最終ダメージ, 技名 or None) を返す"""
        for name, multiplier, prob, line in self.SPECIAL_MOVES:
            if random.random() < prob:
                return int(base_damage * multiplier), f"  ★ 必殺技「{name}」!! 「{line}」"
        return base_damage, None

    def fight(self, opponent: "Yankee") -> "Yankee":
        """喧嘩する"""
        # HP をフルに戻してから開始
        self.hp = self.max_hp
        opponent.hp = opponent.max_hp

        print(f"\n{'='*44}")
        print(f"  ★ {self.name}  VS  {opponent.name} ★")
        print(f"{'='*44}")

        round_num = 1
        while self.hp > 0 and opponent.hp > 0:
            print(f"\n--- ラウンド {round_num} ---")
            time.sleep(0.25)

            # 自分の攻撃
            base = random.randint(10, 30)
            dmg, special_msg = self._try_special(base)
            opponent.hp = max(0, opponent.hp - dmg)
            if special_msg:
                print(special_msg)
            print(f"  {self.name} → {opponent.name} に {dmg} ダメージ！"
                  f"  (残HP: {opponent.hp}/{opponent.max_hp})")

            if opponent.hp <= 0:
                break

            time.sleep(0.25)

            # 相手の攻撃
            base = random.randint(10, 30)
            dmg, special_msg = opponent._try_special(base)
            self.hp = max(0, self.hp - dmg)
            if special_msg:
                print(special_msg)
            print(f"  {opponent.name} → {self.name} に {dmg} ダメージ！"
                  f"  (残HP: {self.hp}/{self.max_hp})")

            round_num += 1
            time.sleep(0.25)

        winner = self if self.hp > 0 else opponent
        loser  = opponent if winner is self else self

        print(f"\n{'='*44}")
        print(f"  勝者: {winner.name}！！  ({round_num} ラウンド)")
        print(f"{'='*44}")
        print(f"{winner.name}: 「立てよ、まだ終わってねーだろ。」")

        winner.respect    += 50
        winner.win_streak += 1
        loser.hp           = 1       # 死なせない（仁義）
        loser.win_streak   = 0

        # ランクアップ通知
        rank, icon = get_rank(winner.respect)
        print(f"  {winner.name} の仁義 → {winner.respect}pt  {icon}{rank}")

        # ライバル設定
        if winner not in loser.rivals:
            loser.rivals.append(winner)
        if loser not in winner.rivals:
            winner.rivals.append(loser)

        return winner

    # ── 回復 ──────────────────────────────────────────────
    def rest(self) -> None:
        """休む（HP回復）"""
        recovered = random.randint(20, 40)
        self.hp = min(self.max_hp, self.hp + recovered)
        print(f"{self.name}: 「…少し休んだ。」  (HP +{recovered} → {self.hp}/{self.max_hp})")

    # ── ステータス ────────────────────────────────────────
    def status(self) -> dict:
        rank, icon = get_rank(self.respect)
        return {
            "name":       self.name,
            "territory":  self.territory,
            "rank":       f"{icon}{rank}",
            "hp":         f"{self.hp}/{self.max_hp}",
            "respect":    self.respect,
            "win_streak": self.win_streak,
            "is_angry":   self.is_angry,
            "rivals":     [r.name for r in self.rivals],
        }


# ─── YankeeGroup クラス ───────────────────────────────────
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
            print(f"  {yankee.name} が 【{self.group_name}】 のボスになった！")
        else:
            print(f"  {yankee.name} が 【{self.group_name}】 に加入した！")

    def challenge_boss(self, challenger: Yankee) -> None:
        """ボスへの挑戦"""
        if self.boss is None:
            print("ボスがいない！")
            return
        if challenger not in self.members:
            print(f"{challenger.name} はメンバーじゃねーぞ！")
            return
        print(f"\n{challenger.name}: 「{self.boss.name}さん、俺に番長の座を賭けて戦ってください！」")
        winner = challenger.fight(self.boss)
        if winner is challenger:
            self.boss = challenger
            print(f"\n  ★ 新ボス誕生 ★  {challenger.name} が 【{self.group_name}】 の番長になった！")

    def group_battle(self, other: "YankeeGroup") -> "YankeeGroup":
        """グループ対抗戦（全員順番に戦う）"""
        print(f"\n{'#'*50}")
        print(f"  グループ対抗戦！！")
        print(f"  【{self.group_name}】 vs 【{other.group_name}】")
        print(f"{'#'*50}")
        our_wins   = 0
        their_wins = 0
        pairs = zip(self.members, other.members)
        for a, b in pairs:
            winner = a.fight(b)
            if winner in self.members:
                our_wins += 1
            else:
                their_wins += 1
        print(f"\n  結果: {self.group_name} {our_wins} - {their_wins} {other.group_name}")
        group_winner = self if our_wins >= their_wins else other
        print(f"  勝利グループ: 【{group_winner.group_name}】！！")
        return group_winner

    def roll_call(self) -> None:
        print(f"\n{'─'*35}")
        print(f"  【{self.group_name}】 点呼！")
        print(f"{'─'*35}")
        for i, member in enumerate(self.members, 1):
            role = "ボス" if member is self.boss else "メンバー"
            rank, icon = get_rank(member.respect)
            print(f"  {i}. {member.name:6s} ({role:4s}) {icon}{rank:4s}  仁義 {member.respect:3d}pt")
        print(f"  総仁義: {self.total_respect()}pt")
        print(f"{'─'*35}")

    def total_respect(self) -> int:
        return sum(m.respect for m in self.members)


# ─── インタラクティブゲーム ───────────────────────────────
def play_interactive() -> None:
    """対話型ヤンキーRPG"""
    print("\n" + "="*50)
    print("  ★ ヤンキーRPG ★  おまえの物語が始まる")
    print("="*50)

    name = input("\nおまえの名前は？ > ").strip() or "名無し"
    territory = input("縄張りは？ > ").strip() or "どこでもない"
    player = Yankee(name, territory)

    enemies = [
        Yankee("チンピラ田中", "路地裏"),
        Yankee("番長ゴロ",    "駅前"),
        Yankee("鉄拳マコト",  "港"),
        Yankee("伝説のリュウ","頂上"),
    ]

    print(f"\n{player.name}、立ち上がれ。お前の前に4人の強敵が立ちはだかっている。")
    time.sleep(0.5)

    for i, enemy in enumerate(enemies, 1):
        print(f"\n{'─'*40}")
        print(f"  第 {i} 戦目  対戦相手: {enemy.name} ({enemy.territory})")
        print(f"{'─'*40}")
        print(f"{enemy.name}: 「", end="")
        enemy.threaten(player.name)

        cmd = input(f"\n[1] 喧嘩する  [2] 仁義を切る  [3] 逃げる > ").strip()

        if cmd == "2":
            player.show_jingi()
            time.sleep(0.3)
            print(f"{enemy.name}: 「……仁義を切る奴は嫌いじゃねーぞ。だが、容赦はしねー！」")
            player.respect += 5

        if cmd == "3":
            print(f"{player.name} は逃げた！  …仁義ポイント -10")
            player.respect = max(0, player.respect - 10)
            continue

        winner = player.fight(enemy)
        if winner is not player:
            print(f"\n{player.name} は倒れた…")
            player.rest()
            player.rest()
            print("だが、立ち上がった。")
        else:
            player.say_cool_thing()

        player.show_face()

        if i < len(enemies):
            input("\n[Enter] で次へ進む...")
        time.sleep(0.2)

    print("\n" + "★"*50)
    rank, icon = get_rank(player.respect)
    print(f"  {player.name}、すべての戦いが終わった。")
    print(f"  ランク: {icon} {rank}")
    print(f"  最終仁義: {player.respect}pt  |  連勝: {player.win_streak}")
    print("★"*50)


# ─── main ─────────────────────────────────────────────────
def main() -> None:
    print("=" * 50)
    print("  不良ヤンキーシミュレーター")
    print("=" * 50)

    # ── キャラクター作成 ──
    takeshi = Yankee("タケシ", "東側")
    ryu     = Yankee("リュウ",  "西側")

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

    print(f"\n最終ステータス:")
    import json
    print(json.dumps(winner.status(), ensure_ascii=False, indent=2))

    # ── グループ対抗戦 ──
    print("\n--- グループ編成 ---")
    east = YankeeGroup("東風連合")
    east.add_member(takeshi)
    east.add_member(Yankee("ケンジ", "東側"))
    east.add_member(Yankee("マサル", "東側"))

    west = YankeeGroup("西日本番長会")
    west.add_member(ryu)
    west.add_member(Yankee("テツ",   "西側"))
    west.add_member(Yankee("ジュン", "西側"))

    east.roll_call()
    west.roll_call()

    east.group_battle(west)

    # ── ボス挑戦 ──
    print("\n--- ボス挑戦 ---")
    east.challenge_boss(east.members[1])  # ケンジがボスに挑戦
    east.roll_call()

    # ── インタラクティブモード ──
    print("\n" + "─"*50)
    ans = input("インタラクティブRPGをプレイしますか？ [y/N] > ").strip().lower()
    if ans == "y":
        play_interactive()


if __name__ == "__main__":
    main()
