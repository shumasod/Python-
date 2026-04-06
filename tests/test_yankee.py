"""
不良ヤンキー テストスイート
"""

import json
import random
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from yankee import (
    Yankee, YankeeGroup, Item, ITEM_CATALOG, SHOP_STOCK,
    get_rank, visit_shop, random_event, show_territory_map,
    STORY_STAGES,
)


# ─── フィクスチャ ──────────────────────────────────────────
@pytest.fixture
def hero():
    return Yankee("テスト太郎", "テスト区")


@pytest.fixture
def rival():
    return Yankee("テスト次郎", "西テスト区")


@pytest.fixture
def iron_pipe():
    return Item("鉄パイプ", atk_bonus=10, description="テスト用")


# ─── get_rank ─────────────────────────────────────────────
class TestGetRank:
    def test_zero_is_chinpira(self):
        title, icon = get_rank(0)
        assert title == "チンピラ"

    def test_thresholds(self):
        assert get_rank(30)[0]  == "一般"
        assert get_rank(60)[0]  == "幹部"
        assert get_rank(100)[0] == "番長"
        assert get_rank(150)[0] == "最強"
        assert get_rank(200)[0] == "伝説"

    def test_exact_boundary(self):
        assert get_rank(29)[0] == "チンピラ"
        assert get_rank(30)[0] == "一般"


# ─── Item ─────────────────────────────────────────────────
class TestItem:
    def test_str_shows_bonuses(self, iron_pipe):
        s = str(iron_pipe)
        assert "鉄パイプ" in s
        assert "ATK+10" in s

    def test_no_bonus_str(self):
        item = Item("ただの石")
        assert "ATK" not in str(item)
        assert "HP"  not in str(item)


# ─── Yankee 基本 ───────────────────────────────────────────
class TestYankeeInit:
    def test_default_stats(self, hero):
        assert hero.hp         == 100
        assert hero.max_hp     == 100
        assert hero.gold       == 0
        assert hero.respect    == 0
        assert hero.base_atk   == 0
        assert hero.win_streak == 0
        assert hero.items      == []
        assert hero.territories_owned == ["テスト区"]

    def test_atk_without_items(self, hero):
        assert hero.atk == 0

    def test_effective_max_hp_without_items(self, hero):
        assert hero.effective_max_hp == 100


# ─── アイテム ─────────────────────────────────────────────
class TestEquip:
    def test_equip_adds_atk(self, hero, iron_pipe):
        hero.equip(iron_pipe)
        assert hero.atk == 10

    def test_equip_adds_hp(self, hero):
        armor = Item("防具", hp_bonus=30)
        hero.equip(armor)
        assert hero.effective_max_hp == 130

    def test_multiple_items_stack(self, hero):
        hero.equip(Item("A", atk_bonus=5))
        hero.equip(Item("B", atk_bonus=3))
        assert hero.atk == 8

    def test_unequip_removes_item(self, hero, iron_pipe):
        hero.equip(iron_pipe)
        result = hero.unequip(iron_pipe.name)
        assert result is True
        assert hero.atk == 0

    def test_unequip_nonexistent_returns_false(self, hero):
        assert hero.unequip("存在しないアイテム") is False


# ─── 修行 ─────────────────────────────────────────────────
class TestTrain:
    def test_train_increases_stats(self, hero, capsys):
        before_atk = hero.base_atk
        before_hp  = hero.max_hp
        hero.train(rounds=5)
        assert hero.base_atk >= before_atk
        assert hero.max_hp   >= before_hp
        assert hero.base_atk + hero.max_hp > before_atk + before_hp

    def test_train_gives_respect(self, hero):
        before = hero.respect
        hero.train(rounds=1)
        assert hero.respect == before + 5


# ─── 戦闘 ─────────────────────────────────────────────────
class TestFight:
    def test_winner_hp_positive(self, hero, rival):
        winner = hero.fight(rival)
        assert winner.hp > 0

    def test_loser_hp_is_one(self, hero, rival):
        winner = hero.fight(rival)
        loser  = rival if winner is hero else hero
        assert loser.hp == 1

    def test_winner_respect_increases(self, hero, rival):
        winner = hero.fight(rival)
        assert winner.respect >= 50

    def test_winner_gold_increases(self, hero, rival):
        before = hero.gold
        winner = hero.fight(rival)
        if winner is hero:
            assert hero.gold > before

    def test_winner_win_streak_increases(self, hero, rival):
        winner = hero.fight(rival)
        assert winner.win_streak == 1

    def test_loser_win_streak_resets(self, hero, rival):
        rival.win_streak = 5
        winner = hero.fight(rival)
        loser  = rival if winner is hero else hero
        assert loser.win_streak == 0

    def test_rivals_registered(self, hero, rival):
        hero.fight(rival)
        assert rival in hero.rivals or hero in rival.rivals

    def test_atk_bonus_applied(self):
        strong = Yankee("強い", "北")
        weak   = Yankee("弱い", "南")
        strong.equip(Item("最強武器", atk_bonus=500))
        winner = strong.fight(weak)
        assert winner is strong

    def test_hp_reset_before_fight(self, hero, rival):
        hero.hp  = 1
        rival.hp = 1
        hero.fight(rival)
        # fight() 冒頭でフルに戻るので少なくとも1ダメージ受けた値になっている
        assert hero.hp != 1 or rival.hp != 1  # 一方は変化している


# ─── 回復 ─────────────────────────────────────────────────
class TestRest:
    def test_rest_increases_hp(self, hero):
        hero.hp = 30
        hero.rest()
        assert hero.hp > 30

    def test_rest_does_not_exceed_max(self, hero):
        hero.hp = hero.effective_max_hp
        hero.rest()
        assert hero.hp == hero.effective_max_hp


# ─── 縄張り ───────────────────────────────────────────────
class TestConquer:
    def test_winner_gains_territory(self):
        attacker = Yankee("攻め", "A地区")
        defender = Yankee("守り", "B地区")
        attacker.equip(Item("最強武器", atk_bonus=1000))
        attacker.conquer(defender)
        assert "B地区" in attacker.territories_owned

    def test_loser_keeps_home_territory(self):
        attacker = Yankee("攻め", "A地区")
        defender = Yankee("守り", "B地区")
        attacker.equip(Item("最強武器", atk_bonus=1000))
        attacker.conquer(defender)
        assert "B地区" in defender.territories_owned


# ─── セーブ/ロード ─────────────────────────────────────────
class TestSaveLoad:
    def test_roundtrip(self, hero, tmp_path):
        hero.equip(ITEM_CATALOG[0])
        hero.respect    = 77
        hero.gold       = 200
        hero.base_atk   = 12
        hero.win_streak = 3
        save_file = tmp_path / "save.json"
        hero.save(save_file)

        loaded = Yankee.load(save_file)
        assert loaded.name        == hero.name
        assert loaded.territory   == hero.territory
        assert loaded.respect     == 77
        assert loaded.gold        == 200
        assert loaded.base_atk    == 12
        assert loaded.win_streak  == 3
        assert loaded.items[0].name == ITEM_CATALOG[0].name

    def test_save_creates_file(self, hero, tmp_path):
        path = tmp_path / "test_save.json"
        hero.save(path)
        assert path.exists()

    def test_load_missing_keys_uses_defaults(self, hero, tmp_path):
        path = tmp_path / "minimal.json"
        path.write_text(
            json.dumps({"name": "最小", "territory": "どこか"}),
            encoding="utf-8",
        )
        y = Yankee.load(path)
        assert y.gold       == 0
        assert y.base_atk   == 0
        assert y.win_streak == 0


# ─── YankeeGroup ─────────────────────────────────────────
class TestYankeeGroup:
    def test_first_member_becomes_boss(self):
        group = YankeeGroup("テスト組")
        a = Yankee("A", "X")
        group.add_member(a)
        assert group.boss is a

    def test_second_member_not_boss(self):
        group = YankeeGroup("テスト組")
        a, b = Yankee("A", "X"), Yankee("B", "Y")
        group.add_member(a)
        group.add_member(b)
        assert group.boss is a

    def test_total_respect(self):
        group = YankeeGroup("テスト組")
        a, b = Yankee("A", "X"), Yankee("B", "Y")
        a.respect, b.respect = 30, 70
        group.add_member(a)
        group.add_member(b)
        assert group.total_respect() == 100

    def test_challenge_boss_winner_becomes_boss(self):
        group = YankeeGroup("テスト組")
        boss       = Yankee("ボス", "X")
        challenger = Yankee("挑戦者", "X")
        challenger.equip(Item("チート武器", atk_bonus=1000))
        group.add_member(boss)
        group.add_member(challenger)
        group.challenge_boss(challenger)
        assert group.boss is challenger

    def test_challenge_boss_non_member_ignored(self):
        group = YankeeGroup("テスト組")
        boss    = Yankee("ボス",   "X")
        outside = Yankee("部外者", "Y")
        group.add_member(boss)
        group.challenge_boss(outside)   # should not crash
        assert group.boss is boss


# ─── ショップ ─────────────────────────────────────────────
class TestShop:
    def test_buy_item_deducts_gold(self):
        player = Yankee("客", "商店街")
        player.gold = 500
        item, price = SHOP_STOCK[0]   # 木刀 50円
        # 入力シミュレーション: [1]=木刀, [0]=退店
        with patch("builtins.input", side_effect=["1", "0"]):
            visit_shop(player)
        assert player.gold == 500 - price
        assert item in player.items

    def test_buy_insufficient_gold(self, capsys):
        player = Yankee("貧乏", "路地裏")
        player.gold = 0
        with patch("builtins.input", side_effect=["1", "0"]):
            visit_shop(player)
        assert not player.items   # 買えていない


# ─── ランダムイベント ─────────────────────────────────────
class TestRandomEvent:
    def test_event_does_not_crash(self, hero):
        for _ in range(20):
            random_event(hero)   # 全イベントパターン網羅


# ─── 縄張りマップ ─────────────────────────────────────────
class TestTerritoryMap:
    def test_owned_territory_highlighted(self, capsys):
        show_territory_map(["東側", "駅前"])
        out = capsys.readouterr().out
        assert "東側" in out
        assert "駅前" in out

    def test_empty_owned(self, capsys):
        show_territory_map([])
        out = capsys.readouterr().out
        assert "なし" in out


# ─── status dict ─────────────────────────────────────────
class TestStatus:
    def test_status_keys(self, hero):
        s = hero.status()
        for key in ("name", "territory", "rank", "hp", "atk", "gold",
                    "respect", "win_streak", "items", "rivals"):
            assert key in s

    def test_status_gold_reflects_value(self, hero):
        hero.gold = 999
        assert hero.status()["gold"] == 999
