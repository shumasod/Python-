"""
不良ヤンキーキャラクター実装
ヤンキー: 日本の不良文化を体現するキャラクター
"""

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ─── アイテム定義 ─────────────────────────────────────────
@dataclass
class Item:
    name: str
    atk_bonus: int = 0      # 攻撃力ボーナス
    hp_bonus: int = 0       # 最大HPボーナス
    description: str = ""

    def __str__(self) -> str:
        parts = []
        if self.atk_bonus:
            parts.append(f"ATK+{self.atk_bonus}")
        if self.hp_bonus:
            parts.append(f"HP+{self.hp_bonus}")
        return f"{self.name} [{', '.join(parts)}] {self.description}"


# 入手可能アイテム一覧
ITEM_CATALOG: list[Item] = [
    Item("木刀",         atk_bonus=5,  hp_bonus=0,  description="基本の得物"),
    Item("鉄パイプ",     atk_bonus=10, hp_bonus=0,  description="重くて痛い"),
    Item("特攻服",       atk_bonus=0,  hp_bonus=20, description="気合が入る"),
    Item("ドカン（ズボン）", atk_bonus=3,  hp_bonus=5,  description="裾広がり"),
    Item("義理の鉢巻き", atk_bonus=5,  hp_bonus=10, description="仲間の想いが宿る"),
    Item("番長の指輪",   atk_bonus=15, hp_bonus=0,  description="伝説の一品"),
]


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
        self.base_atk = 0       # 修行で上がる攻撃力
        self.respect = 0        # 仁義ポイント
        self.is_angry = False
        self.win_streak = 0     # 連勝数
        self.rivals: list["Yankee"] = []
        self.items: list[Item] = []           # 所持アイテム
        self.territories_owned: list[str] = [territory]  # 支配縄張り

    def __repr__(self) -> str:
        rank, icon = get_rank(self.respect)
        return f"<Yankee {icon}{rank} name={self.name!r} territory={self.territory!r} respect={self.respect}>"

    # ── 表示 ──────────────────────────────────────────────
    @property
    def atk(self) -> int:
        """実効攻撃力（基礎 + アイテム）"""
        return self.base_atk + sum(it.atk_bonus for it in self.items)

    @property
    def effective_max_hp(self) -> int:
        return self.max_hp + sum(it.hp_bonus for it in self.items)

    def show_face(self) -> None:
        """ヤンキーの顔を表示"""
        rank, icon = get_rank(self.respect)
        emhp = self.effective_max_hp
        filled = self.hp * 10 // emhp if emhp else 0
        print(self.POMPADOUR)
        print(f"  名前   : {self.name}")
        print(f"  縄張り : {', '.join(self.territories_owned)}")
        print(f"  ランク : {icon} {rank}")
        print(f"  仁義   : {self.respect} pt")
        print(f"  攻撃力 : {self.atk:+d}")
        print(f"  HP     : {'█' * filled}{'░' * (10 - filled)} {self.hp}/{emhp}")
        print(f"  連勝   : {self.win_streak} 連勝")
        if self.items:
            print(f"  装備   : {', '.join(it.name for it in self.items)}")
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

    # ── アイテム ──────────────────────────────────────────
    def equip(self, item: Item) -> None:
        """アイテムを装備する"""
        self.items.append(item)
        bonus_parts = []
        if item.atk_bonus:
            bonus_parts.append(f"攻撃力+{item.atk_bonus}")
        if item.hp_bonus:
            bonus_parts.append(f"最大HP+{item.hp_bonus}")
        bonuses = "、".join(bonus_parts) or "特になし"
        print(f"{self.name}: 「{item.name}を手に入れた。（{bonuses}）」")

    def unequip(self, item_name: str) -> bool:
        for item in self.items:
            if item.name == item_name:
                self.items.remove(item)
                print(f"{self.name}: 「{item_name} を外した。」")
                return True
        return False

    # ── 修行 ──────────────────────────────────────────────
    def train(self, rounds: int = 3) -> None:
        """修行してステータスアップ"""
        TRAINING_MENU = [
            ("腕立て伏せ",   "atk",    3, "拳が鍛えられた！"),
            ("走り込み",     "max_hp", 10, "スタミナがついた！"),
            ("型の練習",     "atk",    5, "技のキレが上がった！"),
            ("断食修行",     "atk",    2, "精神力が増した！"),
        ]
        print(f"\n{self.name}: 「修行を始めるぜ。」")
        for _ in range(rounds):
            t = random.choice(TRAINING_MENU)
            name, stat, amount, msg = t
            time.sleep(0.3)
            print(f"  [{name}]  {msg}", end="  ")
            if stat == "atk":
                self.base_atk += amount
                print(f"攻撃力 +{amount} → {self.atk}")
            else:
                self.max_hp += amount
                print(f"最大HP +{amount} → {self.effective_max_hp}")
        self.respect += 5
        print(f"{self.name}: 「……やってやる。」")

    # ── 縄張り ────────────────────────────────────────────
    def conquer(self, enemy: "Yankee") -> bool:
        """敵に勝って縄張りを奪う"""
        winner = self.fight(enemy)
        if winner is self:
            new_territories = [t for t in enemy.territories_owned
                               if t not in self.territories_owned]
            if new_territories:
                self.territories_owned.extend(new_territories)
                enemy.territories_owned = [enemy.territory]
                print(f"  {self.name} が {', '.join(new_territories)} を支配下に置いた！")
            return True
        return False

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
        self.hp = self.effective_max_hp
        opponent.hp = opponent.effective_max_hp

        print(f"\n{'='*44}")
        print(f"  ★ {self.name}  VS  {opponent.name} ★")
        print(f"{'='*44}")

        round_num = 1
        while self.hp > 0 and opponent.hp > 0:
            print(f"\n--- ラウンド {round_num} ---")
            time.sleep(0.25)

            # 自分の攻撃（atk ボーナス加算）
            base = random.randint(10, 30) + self.atk
            dmg, special_msg = self._try_special(base)
            opponent.hp = max(0, opponent.hp - dmg)
            if special_msg:
                print(special_msg)
            print(f"  {self.name} → {opponent.name} に {dmg} ダメージ！"
                  f"  (残HP: {opponent.hp}/{opponent.effective_max_hp})")

            if opponent.hp <= 0:
                break

            time.sleep(0.25)

            # 相手の攻撃
            base = random.randint(10, 30) + opponent.atk
            dmg, special_msg = opponent._try_special(base)
            self.hp = max(0, self.hp - dmg)
            if special_msg:
                print(special_msg)
            print(f"  {opponent.name} → {self.name} に {dmg} ダメージ！"
                  f"  (残HP: {self.hp}/{self.effective_max_hp})")

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
        emhp = self.effective_max_hp
        self.hp = min(emhp, self.hp + recovered)
        print(f"{self.name}: 「…少し休んだ。」  (HP +{recovered} → {self.hp}/{emhp})")

    # ── ステータス / セーブ ───────────────────────────────
    def status(self) -> dict:
        rank, icon = get_rank(self.respect)
        return {
            "name":              self.name,
            "territory":         self.territory,
            "territories_owned": self.territories_owned,
            "rank":              f"{icon}{rank}",
            "hp":                f"{self.hp}/{self.effective_max_hp}",
            "atk":               self.atk,
            "respect":           self.respect,
            "win_streak":        self.win_streak,
            "is_angry":          self.is_angry,
            "items":             [it.name for it in self.items],
            "rivals":            [r.name for r in self.rivals],
        }

    def save(self, path: str | Path = "yankee_save.json") -> None:
        """セーブデータをJSONに書き出す"""
        data = {
            "name":              self.name,
            "territory":         self.territory,
            "territories_owned": self.territories_owned,
            "max_hp":            self.max_hp,
            "base_atk":          self.base_atk,
            "respect":           self.respect,
            "win_streak":        self.win_streak,
            "items":             [it.name for it in self.items],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [SAVE] {path} にセーブしました。")

    @classmethod
    def load(cls, path: str | Path = "yankee_save.json") -> "Yankee":
        """JSONからヤンキーを復元する"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        y = cls(data["name"], data["territory"])
        y.territories_owned = data.get("territories_owned", [data["territory"]])
        y.max_hp    = data.get("max_hp",    100)
        y.base_atk  = data.get("base_atk",  0)
        y.respect   = data.get("respect",   0)
        y.win_streak = data.get("win_streak", 0)
        catalog = {it.name: it for it in ITEM_CATALOG}
        y.items = [catalog[n] for n in data.get("items", []) if n in catalog]
        print(f"  [LOAD] {path} からロードしました。")
        return y


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
STORY_STAGES = [
    {
        "title":   "第一章  路地裏の洗礼",
        "enemy":   ("チンピラ田中", "路地裏"),
        "item":    ITEM_CATALOG[0],   # 木刀
        "narration": "路地裏に踏み込んだ瞬間、見知らぬ男が立ちはだかった。",
    },
    {
        "title":   "第二章  駅前の覇権",
        "enemy":   ("番長ゴロ",    "駅前"),
        "item":    ITEM_CATALOG[2],   # 特攻服
        "narration": "「この駅前は俺の縄張りだ。通りたければ倒してみろ。」",
    },
    {
        "title":   "第三章  港の鉄拳",
        "enemy":   ("鉄拳マコト",  "港"),
        "item":    ITEM_CATALOG[1],   # 鉄パイプ
        "narration": "港の倉庫に、鉄拳と呼ばれる男が待っていた。",
    },
    {
        "title":   "第四章  頂上決戦",
        "enemy":   ("伝説のリュウ","頂上"),
        "item":    ITEM_CATALOG[5],   # 番長の指輪
        "narration": "頂上。雨の中、伝説と呼ばれる男が一人で立っていた。",
    },
]


def _show_main_menu(player: Yankee, stage_idx: int) -> str:
    rank, icon = get_rank(player.respect)
    emhp = player.effective_max_hp
    filled = player.hp * 10 // emhp if emhp else 0
    print(f"\n  {player.name}  {icon}{rank}  "
          f"HP:{'█'*filled}{'░'*(10-filled)} {player.hp}/{emhp}  "
          f"仁義:{player.respect}pt  ATK:{player.atk:+d}")
    print(f"  縄張り: {', '.join(player.territories_owned)}")
    print(f"{'─'*44}")
    print(f"  [1] 次のステージへ進む  (第{stage_idx+1}章)")
    print(f"  [2] 修行する")
    print(f"  [3] アイテムを見る")
    print(f"  [4] 休む（HP回復）")
    print(f"  [5] セーブ")
    print(f"  [6] ステータス確認")
    print(f"  [0] やめる")
    print(f"{'─'*44}")
    return input("  選択 > ").strip()


def play_interactive(save_path: str = "yankee_save.json") -> None:
    """対話型ヤンキーRPG（メインループ版）"""
    print("\n" + "="*50)
    print("  ★ ヤンキーRPG ★  おまえの物語が始まる")
    print("="*50)

    # ロード or 新規
    if Path(save_path).exists():
        ans = input(f"\nセーブデータが見つかりました。ロードしますか？ [y/N] > ").strip().lower()
        if ans == "y":
            player = Yankee.load(save_path)
        else:
            player = _create_player()
    else:
        player = _create_player()

    stage_idx = min(
        len(STORY_STAGES) - 1,
        len(player.territories_owned) - 1,
    )

    import json as _json
    while stage_idx < len(STORY_STAGES):
        cmd = _show_main_menu(player, stage_idx)

        if cmd == "1":
            stage = STORY_STAGES[stage_idx]
            print(f"\n{'━'*50}")
            print(f"  {stage['title']}")
            print(f"{'━'*50}")
            print(f"\n  {stage['narration']}")
            time.sleep(0.6)

            enemy = Yankee(*stage["enemy"])
            enemy.threaten(player.name)

            sub = input(f"\n  [1] 喧嘩する  [2] 仁義を切る  [3] 逃げる > ").strip()
            if sub == "2":
                player.show_jingi()
                enemy.react("驚")
                player.respect += 5
            elif sub == "3":
                print(f"\n  {player.name} は逃げた……  仁義ポイント -15")
                player.respect = max(0, player.respect - 15)
                continue

            conquered = player.conquer(enemy)
            if conquered:
                player.say_cool_thing()
                reward = stage["item"]
                print(f"\n  ★ 報酬アイテム入手！")
                player.equip(reward)
                stage_idx += 1
                if stage_idx < len(STORY_STAGES):
                    input("\n  [Enter] で次へ…")
            else:
                print(f"\n  {player.name} は倒れた……")
                player.rest()
                player.rest()
                print("  だが、立ち上がった。次こそ勝て。")

        elif cmd == "2":
            rounds = int(input("  何セット修行する？ (1-5) > ").strip() or "3")
            player.train(max(1, min(5, rounds)))

        elif cmd == "3":
            print(f"\n  ── 所持アイテム ──")
            if not player.items:
                print("  （なし）")
            else:
                for i, it in enumerate(player.items, 1):
                    print(f"  {i}. {it}")
            print(f"\n  ── 入手可能アイテム ──")
            for it in ITEM_CATALOG:
                mark = "✓" if it in player.items else " "
                print(f"  [{mark}] {it}")

        elif cmd == "4":
            player.rest()

        elif cmd == "5":
            player.save(save_path)

        elif cmd == "6":
            player.show_face()

        elif cmd == "0":
            print(f"\n  {player.name}: 「また来る。」")
            player.save(save_path)
            return

    # エンディング
    print("\n" + "★"*50)
    rank, icon = get_rank(player.respect)
    print(f"  {player.name}——すべての戦いが終わった。")
    print(f"  ランク  : {icon} {rank}")
    print(f"  最終仁義: {player.respect}pt  |  連勝: {player.win_streak}")
    print(f"  支配縄張り: {', '.join(player.territories_owned)}")
    print("★"*50)
    player.save(save_path)


def _create_player() -> Yankee:
    name = input("\nおまえの名前は？ > ").strip() or "名無し"
    territory = input("縄張りは？ > ").strip() or "どこでもない"
    return Yankee(name, territory)


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
