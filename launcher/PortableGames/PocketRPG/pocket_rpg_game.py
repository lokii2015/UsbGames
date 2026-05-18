#!/usr/bin/env python3
"""UsbGames Pocket RPG — mini JRPG with saves, battles, and dialogue."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame

GAME_ID = "PocketRPG"
WIN_W, WIN_H = 480, 640
FPS_CAP = 60
TILE = 24
MAP_OX, MAP_OY = 16, 72
DIALOG_H = 108
SAMPLE_RATE = 22050

COL_BG = (10, 14, 22)
COL_PANEL = (6, 8, 14)
COL_TURQ = (64, 224, 208)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_RED = (255, 90, 90)
COL_ORANGE = (255, 160, 60)
COL_GOLD = (255, 220, 80)
COL_GRASS = (24, 42, 32)
COL_PATH = (48, 56, 44)
COL_WATER = (28, 52, 88)
COL_WALL = (32, 38, 52)
COL_CAVE = (38, 34, 48)

ITEMS: Dict[str, dict] = {
    "potion": {"name": "Potion", "kind": "heal", "power": 45, "price": 30},
    "ether": {"name": "Ether", "kind": "mp", "power": 30, "price": 35},
    "steel_blade": {"name": "Steel Blade", "kind": "weapon", "atk": 9, "price": 140},
    "chain_mail": {"name": "Chain Mail", "kind": "armor", "def": 6, "price": 110},
}

ENEMIES: Dict[str, dict] = {
    "slime": {"name": "Slime", "hp": 18, "atk": 5, "def": 1, "xp": 8, "gold": 6},
    "bat": {"name": "Bat", "hp": 14, "atk": 7, "def": 0, "xp": 10, "gold": 8},
    "wolf": {"name": "Wolf", "hp": 28, "atk": 10, "def": 2, "xp": 18, "gold": 14},
    "skeleton": {"name": "Skeleton", "hp": 34, "atk": 12, "def": 4, "xp": 24, "gold": 20},
    "boss": {"name": "Crystal Warden", "hp": 95, "atk": 16, "def": 7, "xp": 120, "gold": 200, "boss": True},
}

ENCOUNTERS: Dict[str, List[Tuple[str, float]]] = {
    "forest": [("slime", 0.45), ("bat", 0.35), ("wolf", 0.2)],
    "cave": [("skeleton", 0.55), ("bat", 0.25), ("wolf", 0.2)],
}

DIALOGUE: Dict[str, List[str]] = {
    "elder": [
        "Elder: The Crystal Warden blocks the cave.",
        "Elder: Train in Whisper Woods, then face it.",
        "Elder: Press E near folk and doors to interact.",
    ],
    "merchant": [
        "Merchant: Potions and gear for brave souls.",
        "Merchant: Come back anytime — gold talks.",
    ],
    "guard": [
        "Guard: Woods are dangerous. Stay sharp.",
        "Guard: The boss stole our crystal shard.",
    ],
    "hermit": [
        "Hermit: Fire magic pierces armor well.",
        "Hermit: Save often — Esc opens the menu.",
    ],
    "boss_intro": [
        "Crystal Warden: You shall not pass!",
    ],
    "victory": [
        "The crystal shines again. Oak Village is safe!",
    ],
}


def _parse_map(rows: List[str]) -> dict:
    grid: List[List[str]] = []
    warps: Dict[Tuple[int, int], Tuple[str, int, int]] = {}
    npcs: Dict[Tuple[int, int], str] = {}
    shops: List[Tuple[int, int]] = []
    encounters: List[Tuple[int, int, float]] = []
    for y, row in enumerate(rows):
        line: List[str] = []
        for x, ch in enumerate(row):
            line.append(ch)
            pos = (x, y)
            if ch == "D":
                line[-1] = "."
            elif ch == "N":
                line[-1] = "."
            elif ch == "S":
                line[-1] = "."
                shops.append(pos)
            elif ch == "!":
                line[-1] = "."
                encounters.append((x, y, 0.12))
            elif ch == "T":
                line[-1] = "."
                encounters.append((x, y, 0.22))
            elif ch == "B":
                line[-1] = "."
        grid.append(line)
    return {"grid": grid, "warps": warps, "npcs": npcs, "shops": shops, "encounters": encounters}


MAPS_RAW: Dict[str, dict] = {
    "village": {
        "name": "Oak Village",
        "rows": [
            "####################",
            "#......S...........#",
            "#..N.......N.......#",
            "#..................#",
            "#......####........#",
            "#......#..#........#",
            "#......#..D#########",
            "#......#...........#",
            "#......######......#",
            "#..................#",
            "#..N...............#",
            "#..................#",
            "#........!.........#",
            "#########D##########",
        ],
        "warp_defs": [((9, 13), "forest", 1, 1)],
        "npc_defs": [((3, 2), "elder"), ((12, 2), "merchant"), ((3, 10), "guard")],
    },
    "forest": {
        "name": "Whisper Woods",
        "rows": [
            "####################",
            "D!!!!!!!!!TT!!!!!!!#",
            "#!TT!TT!TT!TT!TT!T!#",
            "#!T!!T!!T!!T!!T!!T!#",
            "#TT!TT!TT!TT!TT!TT!#",
            "#!T!!T!!T!!T!!T!!T!#",
            "#!TT!TT!TT!TT!TT!T!#",
            "#TT!TT!TT!TT!TT!TT!#",
            "#!T!!T!!T!!T!!T!!T!#",
            "#!TT!TT!TT!TT!TT!T!#",
            "#TT!TT!TT!TT!TT!TT!#",
            "#!T!!T!!T!!T!!T!!T!#",
            "#!!!!!!!!!TT!!!!!!!#",
            "###########D########",
        ],
        "warp_defs": [((0, 1), "village", 9, 12), ((11, 13), "cave", 1, 1)],
        "npc_defs": [((17, 5), "hermit")],
    },
    "cave": {
        "name": "Crystal Cave",
        "rows": [
            "####################",
            "D###################",
            "#TTTTTTTTTTTTTTTTT##",
            "#T................T#",
            "#T..TTTT....TTTT..T#",
            "#T..T..T....T..T..T#",
            "#T..T..T....T..T..T#",
            "#T..TTTT....TTTT..T#",
            "#T................T#",
            "#TTTTTTTTTTTTTTTTT##",
            "#..................#",
            "#......TTTT........#",
            "#......T..T........#",
            "#......TB.T........#",
            "####################",
        ],
        "warp_defs": [((0, 1), "forest", 11, 12)],
        "npc_defs": [],
        "boss": (9, 13),
    },
}


def build_maps() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for mid, spec in MAPS_RAW.items():
        parsed = _parse_map(spec["rows"])
        for (x, y), tid, tx, ty in spec.get("warp_defs", []):
            parsed["warps"][(x, y)] = (tid, tx, ty)
        for (x, y), nid in spec.get("npc_defs", []):
            parsed["npcs"][(x, y)] = nid
        parsed["name"] = spec["name"]
        parsed["boss"] = spec.get("boss")
        out[mid] = parsed
    return out


MAPS = build_maps()


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower().replace(" ", "") in ("pocketrpg",):
        parent = os.path.dirname(d)
        if os.path.basename(parent).lower() == "portablegames":
            return os.path.dirname(parent)
    return None



def _web_profile() -> bool:
    """Download / launcher-sync builds use web profile (stats on account page only)."""
    if os.environ.get("USBGAMES_PROFILE", "").strip().lower() == "web":
        return True
    try:
        with open(os.path.join(app_dir(), "game.json"), "r", encoding="utf-8") as f:
            if json.load(f).get("profile") == "web":
                return True
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return False

def profile_path() -> Optional[str]:
    if _web_profile():
        return None
    root = usb_root()
    if not root:
        return None
    profiles = os.path.join(root, "UsbGames", "profiles")
    try:
        os.makedirs(profiles, exist_ok=True)
    except OSError:
        return None
    return os.path.join(profiles, "default.json")


SAVE_PATH = os.path.join(app_dir(), "save.json")
STATS_PATH = os.path.join(app_dir(), "stats.json")


def _tone(freq: float, ms: int, volume: float = 0.3) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * ms / 1000)
    amp = int(32767 * volume)
    buf = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        env = min(1.0, i / (n * 0.05), (n - i) / (n * 0.12))
        sample = int(amp * env * math.sin(2 * math.pi * freq * t))
        buf.extend(struct.pack("<h", sample))
    return pygame.mixer.Sound(buffer=bytes(buf))


class Audio:
    def __init__(self) -> None:
        self.enabled = True
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.ui = _tone(520, 40, 0.2)
            self.hit = _tone(180, 60, 0.25)
            self.magic = _tone(660, 70, 0.22)
            self.win = _tone(720, 100, 0.25)
            self.step = _tone(300, 25, 0.08)
            self.save = _tone(440, 50, 0.2)
        except pygame.error:
            self.enabled = False

    def play(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and snd:
            snd.play()


def load_json(path: str, default: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {**default, **json.load(f)}
    except (OSError, json.JSONDecodeError):
        return default.copy()


def save_json(path: str, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def default_player() -> dict:
    return {
        "map_id": "village",
        "x": 5,
        "y": 5,
        "level": 1,
        "xp": 0,
        "hp": 35,
        "max_hp": 35,
        "mp": 12,
        "max_mp": 12,
        "atk": 8,
        "def": 3,
        "gold": 50,
        "weapon": None,
        "armor": None,
        "inventory": {"potion": 2, "ether": 1},
        "flags": {"boss_defeated": False},
    }


def xp_for_level(lv: int) -> int:
    return 25 + (lv - 1) * 20


def load_save() -> dict:
    data = load_json(SAVE_PATH, {"player": default_player(), "play_time": 0})
    p = data.get("player", {})
    base = default_player()
    base.update({k: p[k] for k in p if k in base or k == "flags"})
    if "flags" in p:
        base["flags"].update(p["flags"])
    data["player"] = base
    return data


def save_game(data: dict) -> None:
    save_json(SAVE_PATH, data)
    prof = profile_path()
    if prof:
        root = load_json(prof, {"profile": "default", "games": {}})
        g = root.setdefault("games", {}).setdefault(GAME_ID, {})
        g["cleared"] = data["player"]["flags"].get("boss_defeated", False)
        g["level"] = data["player"]["level"]
        save_json(prof, root)


def load_stats() -> dict:
    return load_json(STATS_PATH, {"clears": 0, "sessions": 0})


def save_stats(st: dict) -> None:
    save_json(STATS_PATH, st)


class Screen(Enum):
    TITLE = auto()
    OVERWORLD = auto()
    DIALOGUE = auto()
    BATTLE = auto()
    MENU = auto()
    SHOP = auto()
    VICTORY = auto()


@dataclass
class Fighter:
    name: str
    hp: int
    max_hp: int
    atk: int
    def_: int
    mp: int = 0
    max_mp: int = 0
    is_player: bool = False
    enemy_id: Optional[str] = None


class PocketRPGGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Pocket RPG — UsbGames")
        self._display = pygame.display.set_mode((WIN_W, WIN_H))
        self.canvas = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 26, bold=True)
        self.font_md = pygame.font.SysFont("courier", 18, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 15)
        self.font_xs = pygame.font.SysFont("courier", 12)

        self.audio = Audio()
        self.stats = load_stats()
        self.save_data = load_save()
        self.player = self.save_data["player"]
        self.screen_id = Screen.TITLE
        self._buttons: List[Tuple[pygame.Rect, str]] = []
        self._hover: Optional[int] = None

        self.dialogue_id = ""
        self.dialogue_idx = 0
        self.menu_sel = 0
        self.shop_sel = 0
        self.battle_menu = 0
        self.battle_phase = "menu"
        self.battle_msg = ""
        self.battle_timer = 0.0
        self.player_fighter: Optional[Fighter] = None
        self.enemy_fighter: Optional[Fighter] = None
        self.is_boss_battle = False
        self._move_cooldown = 0.0
        self._step_snd = 0.0
        self._pending_boss = False
        self._dialogue_lines: List[str] = []

    def _pixel_text(self, text: str, x: int, y: int, font: pygame.font.Font, color: Tuple[int, int, int], center: bool = False) -> None:
        surf = font.render(text, True, color)
        rx = x - surf.get_width() // 2 if center else x
        self.canvas.blit(surf, (rx, y))

    def _player_stats(self) -> Tuple[int, int]:
        p = self.player
        atk = p["atk"] + (ITEMS[p["weapon"]]["atk"] if p.get("weapon") else 0)
        def_ = p["def"] + (ITEMS[p["armor"]]["def"] if p.get("armor") else 0)
        return atk, def_

    def _level_up(self) -> None:
        p = self.player
        while p["xp"] >= xp_for_level(p["level"]):
            p["xp"] -= xp_for_level(p["level"])
            p["level"] += 1
            p["max_hp"] += 8
            p["max_mp"] += 4
            p["atk"] += 2
            p["def"] += 1
            p["hp"] = p["max_hp"]
            p["mp"] = p["max_mp"]
            self.battle_msg = f"LEVEL UP! Now level {p['level']}."

    def _warp_if_needed(self) -> None:
        m = MAPS[self.player["map_id"]]
        pos = (self.player["x"], self.player["y"])
        if pos in m["warps"]:
            tid, tx, ty = m["warps"][pos]
            self.player["map_id"] = tid
            self.player["x"] = tx
            self.player["y"] = ty
            self._persist()

    def _persist(self) -> None:
        self.save_data["player"] = self.player
        save_game(self.save_data)

    def _start_dialogue(self, dlg_id: str) -> None:
        lines = DIALOGUE.get(dlg_id, ["..."])
        self.dialogue_id = dlg_id
        self.dialogue_idx = 0
        self.screen_id = Screen.DIALOGUE
        self._dialogue_lines = lines

    def _try_interact(self) -> None:
        p = self.player
        m = MAPS[p["map_id"]]
        for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)):
            pos = (p["x"] + dx, p["y"] + dy)
            if pos in m["npcs"]:
                self._start_dialogue(m["npcs"][pos])
                return
            if pos in m["warps"]:
                self.audio.play(self.audio.ui)
                return
        for sx, sy in m["shops"]:
            if abs(p["x"] - sx) + abs(p["y"] - sy) <= 1:
                self.shop_sel = 0
                self.screen_id = Screen.SHOP
                return
        if p["map_id"] == "cave" and m.get("boss") and not p["flags"].get("boss_defeated"):
            bx, by = m["boss"]
            if abs(p["x"] - bx) + abs(p["y"] - by) <= 1:
                self._start_boss()

    def _roll_encounter(self) -> None:
        p = self.player
        m = MAPS[p["map_id"]]
        pool = ENCOUNTERS.get(p["map_id"])
        if not pool:
            return
        for ex, ey, rate in m["encounters"]:
            if p["x"] == ex and p["y"] == ey and random.random() < rate:
                roll = random.random()
                acc = 0.0
                for eid, w in pool:
                    acc += w
                    if roll <= acc:
                        self._start_battle(eid)
                        return

    def _start_battle(self, enemy_id: str) -> None:
        spec = ENEMIES[enemy_id]
        self.is_boss_battle = spec.get("boss", False)
        pa, pd = self._player_stats()
        p = self.player
        self.player_fighter = Fighter("Hero", p["hp"], p["max_hp"], pa, pd, p["mp"], p["max_mp"], True)
        self.enemy_fighter = Fighter(spec["name"], spec["hp"], spec["hp"], spec["atk"], spec["def"], enemy_id=enemy_id)
        self.battle_menu = 0
        self.battle_phase = "menu"
        self.battle_msg = f"A {spec['name']} appears!"
        self.battle_timer = 0.0
        self.screen_id = Screen.BATTLE

    def _start_boss(self) -> None:
        self._start_dialogue("boss_intro")
        self._pending_boss = True

    def _move_player(self, dx: int, dy: int) -> None:
        if self._move_cooldown > 0:
            return
        p = self.player
        m = MAPS[p["map_id"]]
        nx, ny = p["x"] + dx, p["y"] + dy
        if ny < 0 or ny >= len(m["grid"]) or nx < 0 or nx >= len(m["grid"][0]):
            return
        tile = m["grid"][ny][nx]
        if tile == "#" or tile == "~":
            return
        p["x"], p["y"] = nx, ny
        self._move_cooldown = 0.14
        self._step_snd += 1
        if self._step_snd % 2 == 0:
            self.audio.play(self.audio.step)
        self._warp_if_needed()
        self._roll_encounter()

    def _battle_damage(self, atk: int, def_: int) -> int:
        return max(1, atk - def_ // 2 + random.randint(-1, 2))

    def _battle_player_action(self, action: str) -> None:
        pf = self.player_fighter
        ef = self.enemy_fighter
        if not pf or not ef:
            return
        p = self.player
        if action == "attack":
            dmg = self._battle_damage(pf.atk, ef.def_)
            ef.hp -= dmg
            self.battle_msg = f"You hit for {dmg}!"
            self.audio.play(self.audio.hit)
        elif action == "fire":
            if p["mp"] < 5:
                self.battle_msg = "Not enough MP!"
                self.battle_phase = "menu"
                return
            p["mp"] -= 5
            pf.mp = p["mp"]
            dmg = self._battle_damage(pf.atk + 10, max(0, ef.def_ - 2))
            ef.hp -= dmg
            self.battle_msg = f"Fire hits for {dmg}!"
            self.audio.play(self.audio.magic)
        elif action == "item":
            if p["inventory"].get("potion", 0) > 0:
                p["inventory"]["potion"] -= 1
                heal = min(ITEMS["potion"]["power"], p["max_hp"] - p["hp"])
                p["hp"] += heal
                pf.hp = p["hp"]
                self.battle_msg = f"Potion heals {heal} HP!"
                self.audio.play(self.audio.ui)
            else:
                self.battle_msg = "No potions!"
                self.battle_phase = "menu"
                return
        elif action == "run":
            if self.is_boss_battle:
                self.battle_msg = "Can't run from the boss!"
                self.battle_phase = "menu"
                return
            if random.random() < 0.65:
                self.screen_id = Screen.OVERWORLD
                self._sync_player_from_fighter()
                return
            self.battle_msg = "Couldn't escape!"

        if ef.hp <= 0:
            self._battle_win()
            return
        self.battle_phase = "enemy"

    def _battle_enemy_turn(self) -> None:
        pf = self.player_fighter
        ef = self.enemy_fighter
        if not pf or not ef:
            return
        if random.random() < 0.2 and not self.is_boss_battle:
            self.battle_msg = f"{ef.name} hesitates."
        else:
            dmg = self._battle_damage(ef.atk, pf.def_)
            pf.hp -= dmg
            self.player["hp"] = pf.hp
            self.battle_msg = f"{ef.name} hits for {dmg}!"
            self.audio.play(self.audio.hit)
        if pf.hp <= 0:
            self.battle_msg = "You were defeated..."
            self.battle_timer = 1.2
            self.battle_phase = "lose"
            return
        self.battle_phase = "menu"

    def _sync_player_from_fighter(self) -> None:
        if self.player_fighter:
            self.player["hp"] = max(1, self.player_fighter.hp)
            self.player["mp"] = self.player_fighter.mp

    def _battle_win(self) -> None:
        ef = self.enemy_fighter
        if not ef or not ef.enemy_id:
            return
        spec = ENEMIES[ef.enemy_id]
        p = self.player
        p["gold"] += spec["gold"]
        p["xp"] += spec["xp"]
        self.battle_msg = f"Won! +{spec['xp']} XP, +{spec['gold']} gold."
        self.audio.play(self.audio.win)
        self._level_up()
        if spec.get("boss"):
            p["flags"]["boss_defeated"] = True
            st = load_stats()
            st["clears"] = int(st.get("clears", 0)) + 1
            save_stats(st)
            self.stats = load_stats()
            self.battle_phase = "victory"
        else:
            self.battle_phase = "won"
        self.battle_timer = 1.0
        self._sync_player_from_fighter()
        self._persist()

    def _use_menu_item(self, item_id: str) -> None:
        p = self.player
        if p["inventory"].get(item_id, 0) <= 0:
            return
        kind = ITEMS[item_id]["kind"]
        if kind == "heal":
            if p["hp"] >= p["max_hp"]:
                return
            p["inventory"][item_id] -= 1
            p["hp"] = min(p["max_hp"], p["hp"] + ITEMS[item_id]["power"])
        elif kind == "mp":
            if p["mp"] >= p["max_mp"]:
                return
            p["inventory"][item_id] -= 1
            p["mp"] = min(p["max_mp"], p["mp"] + ITEMS[item_id]["power"])
        elif kind == "weapon":
            old = p.get("weapon")
            if old:
                p["inventory"][old] = p["inventory"].get(old, 0) + 1
            p["inventory"][item_id] -= 1
            p["weapon"] = item_id
        elif kind == "armor":
            old = p.get("armor")
            if old:
                p["inventory"][old] = p["inventory"].get(old, 0) + 1
            p["inventory"][item_id] -= 1
            p["armor"] = item_id
        self.audio.play(self.audio.ui)
        self._persist()

    def _buy_item(self, item_id: str) -> None:
        p = self.player
        price = ITEMS[item_id]["price"]
        if p["gold"] < price:
            return
        p["gold"] -= price
        p["inventory"][item_id] = p["inventory"].get(item_id, 0) + 1
        self.audio.play(self.audio.ui)
        self._persist()

    def _tile_color(self, map_id: str, tile: str) -> Tuple[int, int, int]:
        if map_id == "cave":
            if tile == "#":
                return COL_WALL
            if tile == "~":
                return COL_WATER
            return COL_CAVE
        if tile == "#":
            return COL_WALL
        if tile == "~":
            return COL_WATER
        return COL_GRASS if map_id == "forest" else COL_PATH

    def _draw_overworld(self) -> None:
        p = self.player
        m = MAPS[p["map_id"]]
        grid = m["grid"]
        rows, cols = len(grid), len(grid[0])
        self._pixel_text(m["name"], WIN_W // 2, 12, self.font_md, COL_TURQ, center=True)
        for y in range(rows):
            for x in range(cols):
                tile = grid[y][x]
                rx = MAP_OX + x * TILE
                ry = MAP_OY + y * TILE
                pygame.draw.rect(self.canvas, self._tile_color(p["map_id"], tile), (rx, ry, TILE - 1, TILE - 1))
        px = MAP_OX + p["x"] * TILE + TILE // 2
        py = MAP_OY + p["y"] * TILE + TILE // 2
        pygame.draw.rect(self.canvas, COL_TURQ, (px - 8, py - 8, 16, 16), border_radius=3)
        pygame.draw.rect(self.canvas, COL_TEXT, (px - 8, py - 8, 16, 16), 1, border_radius=3)
        for (nx, ny), _ in m["npcs"].items():
            rx = MAP_OX + nx * TILE + 6
            ry = MAP_OY + ny * TILE + 4
            pygame.draw.rect(self.canvas, COL_ORANGE, (rx, ry, 12, 14))
        if p["map_id"] == "cave" and m.get("boss") and not p["flags"].get("boss_defeated"):
            bx, by = m["boss"]
            rx = MAP_OX + bx * TILE + 4
            ry = MAP_OY + by * TILE + 2
            pygame.draw.rect(self.canvas, COL_RED, (rx, ry, 16, 18))
        self._draw_hud_bar()

    def _draw_hud_bar(self) -> None:
        p = self.player
        pygame.draw.rect(self.canvas, COL_PANEL, (0, WIN_H - 52, WIN_W, 52))
        self._pixel_text(f"LV{p['level']}", 8, WIN_H - 44, self.font_sm, COL_TURQ)
        self._pixel_text(f"HP {p['hp']}/{p['max_hp']}", 50, WIN_H - 44, self.font_xs, COL_GREEN)
        self._pixel_text(f"MP {p['mp']}/{p['max_mp']}", 50, WIN_H - 28, self.font_xs, COL_TURQ)
        self._pixel_text(f"G {p['gold']}", WIN_W - 70, WIN_H - 44, self.font_sm, COL_GOLD)
        self._pixel_text("E TALK  ESC MENU", WIN_W // 2, WIN_H - 18, self.font_xs, COL_DIM, center=True)

    def _draw_dialogue(self) -> None:
        self._draw_overworld()
        pygame.draw.rect(self.canvas, COL_PANEL, (8, WIN_H - DIALOG_H - 56, WIN_W - 16, DIALOG_H))
        pygame.draw.rect(self.canvas, COL_TURQ, (8, WIN_H - DIALOG_H - 56, WIN_W - 16, DIALOG_H), 2)
        line = self._dialogue_lines[min(self.dialogue_idx, len(self._dialogue_lines) - 1)]
        self._pixel_text(line, 20, WIN_H - DIALOG_H - 30, self.font_sm, COL_TEXT)
        self._pixel_text("ENTER / E — next", WIN_W - 16, WIN_H - 70, self.font_xs, COL_DIM, center=False)

    def _draw_battle(self) -> None:
        self.canvas.fill(COL_BG)
        pf = self.player_fighter
        ef = self.enemy_fighter
        if pf:
            self._pixel_text(f"HERO  HP {pf.hp}/{pf.max_hp}  MP {pf.mp}/{pf.max_mp}", 16, 24, self.font_sm, COL_GREEN)
        if ef:
            self._pixel_text(ef.name, WIN_W - 16, 24, self.font_sm, COL_RED, center=False)
            surf = self.font_sm.render(ef.name, True, COL_RED)
            self.canvas.blit(surf, (WIN_W - surf.get_width() - 16, 24))
            self._pixel_text(f"HP {max(0, ef.hp)}/{ef.max_hp}", WIN_W - 16, 44, self.font_xs, COL_DIM, center=False)
            surf2 = self.font_xs.render(f"HP {max(0, ef.hp)}/{ef.max_hp}", True, COL_DIM)
            self.canvas.blit(surf2, (WIN_W - surf2.get_width() - 16, 44))
        pygame.draw.rect(self.canvas, COL_TURQ, (40, 120, 80, 80), border_radius=4)
        pygame.draw.rect(self.canvas, COL_RED, (WIN_W - 120, 100, 80, 80), border_radius=4)
        pygame.draw.rect(self.canvas, COL_PANEL, (8, 400, WIN_W - 16, 120))
        self._pixel_text(self.battle_msg, 20, 420, self.font_sm, COL_TEXT)
        if self.battle_phase == "menu":
            opts = ["ATTACK", "FIRE (5 MP)", "POTION", "RUN"]
            y = 460
            for i, opt in enumerate(opts):
                col = COL_TURQ if i == self.battle_menu else COL_DIM
                self._pixel_text(f"{'>' if i == self.battle_menu else ' '} {opt}", 24, y + i * 18, self.font_xs, col)

    def _draw_menu(self) -> None:
        self._draw_overworld()
        pygame.draw.rect(self.canvas, (0, 0, 0, 160), (0, 0, WIN_W, WIN_H))
        pygame.draw.rect(self.canvas, COL_PANEL, (60, 80, WIN_W - 120, 380))
        pygame.draw.rect(self.canvas, COL_TURQ, (60, 80, WIN_W - 120, 380), 2)
        p = self.player
        pa, pd = self._player_stats()
        lines = [
            "=== HERO ===",
            f"LV {p['level']}  XP {p['xp']}/{xp_for_level(p['level'])}",
            f"HP {p['hp']}/{p['max_hp']}  MP {p['mp']}/{p['max_mp']}",
            f"ATK {pa}  DEF {pd}",
            f"WPN {ITEMS[p['weapon']]['name'] if p.get('weapon') else 'None'}",
            f"ARM {ITEMS[p['armor']]['name'] if p.get('armor') else 'None'}",
            "",
            "=== ITEMS ===",
        ]
        inv_lines = [f"  {ITEMS[k]['name']} x{v}" for k, v in sorted(p["inventory"].items()) if v > 0]
        if not inv_lines:
            inv_lines = ["  (empty)"]
        menu_opts = ["Use Potion", "Use Ether", "Save Game", "Close"]
        y = 100
        for ln in lines + inv_lines:
            self._pixel_text(ln, 80, y, self.font_xs, COL_TEXT)
            y += 16
        y += 8
        for i, opt in enumerate(menu_opts):
            col = COL_TURQ if i == self.menu_sel else COL_DIM
            self._pixel_text(f"{'>' if i == self.menu_sel else ' '} {opt}", 80, y + i * 20, self.font_sm, col)

    def _draw_shop(self) -> None:
        self._draw_overworld()
        pygame.draw.rect(self.canvas, COL_PANEL, (40, 90, WIN_W - 80, 360))
        pygame.draw.rect(self.canvas, COL_GOLD, (40, 90, WIN_W - 80, 360), 2)
        self._pixel_text("MERCHANT SHOP", WIN_W // 2, 108, self.font_md, COL_GOLD, center=True)
        self._pixel_text(f"Your gold: {self.player['gold']}", WIN_W // 2, 132, self.font_sm, COL_TEXT, center=True)
        shop_items = ["potion", "ether", "steel_blade", "chain_mail"]
        y = 160
        for i, iid in enumerate(shop_items):
            it = ITEMS[iid]
            col = COL_TURQ if i == self.shop_sel else COL_DIM
            self._pixel_text(f"{'>' if i == self.shop_sel else ' '} {it['name']} — {it['price']}G", 60, y + i * 28, self.font_sm, col)
        self._pixel_text("ENTER buy   ESC leave", WIN_W // 2, 420, self.font_xs, COL_DIM, center=True)

    def _draw_title(self) -> None:
        self._pixel_text("POCKET RPG", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames Premium", WIN_W // 2, 135, self.font_sm, COL_DIM, center=True)
        cleared = int(self.stats.get("clears", 0))
        self._pixel_text(f"QUESTS CLEARED {cleared}", WIN_W // 2, 170, self.font_md, COL_GREEN, center=True)
        has_save = os.path.isfile(SAVE_PATH)
        y = 220
        if has_save:
            p = self.player
            self._pixel_text(f"Continue — LV{p['level']} {MAPS[p['map_id']]['name']}", WIN_W // 2, y, self.font_sm, COL_TEXT, center=True)
            y += 36
        self._pixel_text("ENTER — " + ("Continue" if has_save else "New Quest"), WIN_W // 2, y, self.font_md, COL_TURQ, center=True)
        if has_save:
            self._pixel_text("N — New Game", WIN_W // 2, y + 36, self.font_sm, COL_DIM, center=True)
        self._pixel_text("ARROWS move · E talk · TURN-BASED BATTLES", WIN_W // 2, 380, self.font_xs, COL_DIM, center=True)

    def _draw_victory(self) -> None:
        self.canvas.fill(COL_BG)
        self._pixel_text("VICTORY!", WIN_W // 2, 140, self.font_lg, COL_GREEN, center=True)
        for i, line in enumerate(DIALOGUE["victory"]):
            self._pixel_text(line, WIN_W // 2, 200 + i * 24, self.font_sm, COL_TEXT, center=True)
        self._pixel_text("ENTER — return to village", WIN_W // 2, 400, self.font_sm, COL_TURQ, center=True)

    def draw(self) -> None:
        self.canvas.fill(COL_BG)
        if self.screen_id == Screen.TITLE:
            self._draw_title()
        elif self.screen_id == Screen.OVERWORLD:
            self._draw_overworld()
        elif self.screen_id == Screen.DIALOGUE:
            self._draw_dialogue()
        elif self.screen_id == Screen.BATTLE:
            self._draw_battle()
        elif self.screen_id == Screen.MENU:
            self._draw_menu()
        elif self.screen_id == Screen.SHOP:
            self._draw_shop()
        elif self.screen_id == Screen.VICTORY:
            self._draw_victory()
        self._display.blit(self.canvas, (0, 0))
        pygame.display.flip()

    def update(self, dt: float) -> None:
        self._move_cooldown = max(0.0, self._move_cooldown - dt)
        if self.screen_id == Screen.BATTLE:
            self.battle_timer -= dt
            if self.battle_phase == "enemy" and self.battle_timer <= 0:
                self._battle_enemy_turn()
                self.battle_timer = 0.6
            elif self.battle_phase in ("won", "victory") and self.battle_timer <= 0:
                if self.battle_phase == "victory":
                    self.screen_id = Screen.VICTORY
                else:
                    self.screen_id = Screen.OVERWORLD
            elif self.battle_phase == "lose" and self.battle_timer <= 0:
                p = self.player
                p["hp"] = p["max_hp"] // 2
                p["map_id"] = "village"
                p["x"], p["y"] = 5, 5
                self._persist()
                self.screen_id = Screen.OVERWORLD

    def _new_game(self) -> None:
        self.player = default_player()
        self.save_data = {"player": self.player, "play_time": 0}
        self._persist()
        st = load_stats()
        st["sessions"] = int(st.get("sessions", 0)) + 1
        save_stats(st)
        self.stats = load_stats()
        self.screen_id = Screen.OVERWORLD

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if self.screen_id == Screen.TITLE:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if os.path.isfile(SAVE_PATH):
                    self.save_data = load_save()
                    self.player = self.save_data["player"]
                    self.screen_id = Screen.OVERWORLD
                else:
                    self._new_game()
            elif event.key == pygame.K_n:
                self._new_game()
            return

        if self.screen_id == Screen.VICTORY:
            if event.key in (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE):
                self.player["map_id"] = "village"
                self.player["x"], self.player["y"] = 5, 5
                self._persist()
                self.screen_id = Screen.OVERWORLD
            return

        if self.screen_id == Screen.DIALOGUE:
            if event.key in (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE):
                if self.dialogue_idx + 1 < len(self._dialogue_lines):
                    self.dialogue_idx += 1
                else:
                    if getattr(self, "_pending_boss", False):
                        self._pending_boss = False
                        self._start_battle("boss")
                    else:
                        self.screen_id = Screen.OVERWORLD
            elif event.key == pygame.K_ESCAPE:
                self.screen_id = Screen.OVERWORLD
            return

        if self.screen_id == Screen.SHOP:
            shop_items = ["potion", "ether", "steel_blade", "chain_mail"]
            if event.key in (pygame.K_UP, pygame.K_w):
                self.shop_sel = (self.shop_sel - 1) % len(shop_items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.shop_sel = (self.shop_sel + 1) % len(shop_items)
            elif event.key in (pygame.K_RETURN, pygame.K_e):
                self._buy_item(shop_items[self.shop_sel])
            elif event.key == pygame.K_ESCAPE:
                self.screen_id = Screen.OVERWORLD
            return

        if self.screen_id == Screen.MENU:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.menu_sel = (self.menu_sel - 1) % 4
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_sel = (self.menu_sel + 1) % 4
            elif event.key in (pygame.K_RETURN, pygame.K_e):
                if self.menu_sel == 0:
                    self._use_menu_item("potion")
                elif self.menu_sel == 1:
                    self._use_menu_item("ether")
                elif self.menu_sel == 2:
                    self._persist()
                    self.audio.play(self.audio.save)
                else:
                    self.screen_id = Screen.OVERWORLD
            elif event.key == pygame.K_ESCAPE:
                self.screen_id = Screen.OVERWORLD
            return

        if self.screen_id == Screen.BATTLE:
            if self.battle_phase == "menu":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.battle_menu = (self.battle_menu - 1) % 4
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.battle_menu = (self.battle_menu + 1) % 4
                elif event.key in (pygame.K_RETURN, pygame.K_e):
                    acts = ["attack", "fire", "item", "run"]
                    self._battle_player_action(acts[self.battle_menu])
                    if self.battle_phase == "enemy":
                        self.battle_timer = 0.7
            return

        if self.screen_id == Screen.OVERWORLD:
            if event.key == pygame.K_ESCAPE:
                self.menu_sel = 0
                self.screen_id = Screen.MENU
            elif event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self._try_interact()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._move_player(0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move_player(0, 1)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._move_player(-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._move_player(1, 0)

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(FPS_CAP) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()


def main() -> None:
    PocketRPGGame().run()


if __name__ == "__main__":
    main()
