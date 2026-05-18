#!/usr/bin/env python3
"""UsbGames Grid Defense — tower defense with maps and unlocks."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

import pygame

GAME_ID = "GridDefense"
LOG_W, LOG_H = 480, 640
FPS_CAP = 60
HUD_H = 44
ACTION_H = 30
BAR_H = 80
MAX_TOWER_LEVEL = 3
SELL_REFUND_RATE = 0.65
UPGRADE_COST_FACTOR = 0.55

COL_BG = (10, 14, 22)
COL_GRID = (18, 24, 34)
COL_PATH = (32, 42, 58)
COL_PATH_EDGE = (64, 224, 208)
COL_TURQ = (64, 224, 208)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_RED = (255, 90, 90)
COL_ORANGE = (255, 160, 60)
COL_LOCKED = (55, 60, 70)

SAMPLE_RATE = 22050

TOWER_TYPES: Dict[str, dict] = {
    "blaster": {"name": "BLASTER", "cost": 40, "range": 3.0, "damage": 1, "cooldown": 0.5, "color": COL_TURQ, "unlock": 0},
    "rapid": {"name": "RAPID", "cost": 55, "range": 2.6, "damage": 1, "cooldown": 0.22, "color": COL_GREEN, "unlock": 1},
    "sniper": {"name": "SNIPER", "cost": 85, "range": 5.5, "damage": 4, "cooldown": 1.3, "color": (120, 180, 255), "unlock": 2},
    "cannon": {"name": "CANNON", "cost": 110, "range": 3.8, "damage": 5, "cooldown": 1.0, "color": COL_ORANGE, "unlock": 3},
    "frost": {"name": "FROST", "cost": 95, "range": 3.2, "damage": 1, "cooldown": 0.7, "color": (140, 220, 255), "unlock": 4, "slow": 0.45},
    "splash": {"name": "SPLASH", "cost": 130, "range": 3.5, "damage": 2, "cooldown": 0.9, "color": (255, 120, 80), "unlock": 5, "splash": 36},
    "laser": {"name": "LASER", "cost": 150, "range": 4.2, "damage": 2, "cooldown": 0.35, "color": (255, 80, 200), "unlock": 6},
    "mortar": {"name": "MORTAR", "cost": 175, "range": 4.8, "damage": 4, "cooldown": 1.4, "color": (200, 140, 80), "unlock": 8, "splash": 52},
    "tesla": {"name": "TESLA", "cost": 200, "range": 3.0, "damage": 2, "cooldown": 0.6, "color": (180, 255, 120), "unlock": 10, "chain": 2},
    "rail": {"name": "RAIL", "cost": 240, "range": 5.0, "damage": 6, "cooldown": 1.6, "color": (220, 220, 255), "unlock": 12},
    "nano": {"name": "NANO", "cost": 25, "range": 2.2, "damage": 1, "cooldown": 0.4, "color": (160, 160, 180), "unlock": 14},
    "core": {"name": "CORE", "cost": 350, "range": 4.5, "damage": 8, "cooldown": 1.8, "color": (255, 230, 120), "unlock": 18},
}
TOWER_ORDER = list(TOWER_TYPES.keys())


def _path_from_segments(cols: int, rows: int, segments: List[Tuple[str, int, int, int]]) -> Set[Tuple[int, int]]:
    """segments: list of ('h'|'v', fixed_coord, start, end) on grid."""
    cells: Set[Tuple[int, int]] = set()
    for kind, fixed, a, b in segments:
        lo, hi = min(a, b), max(a, b)
        if kind == "h":
            for c in range(lo, hi + 1):
                if 0 <= c < cols and 0 <= fixed < rows:
                    cells.add((c, fixed))
        else:
            for r in range(lo, hi + 1):
                if 0 <= fixed < cols and 0 <= r < rows:
                    cells.add((fixed, r))
    return cells


def _waypoints_from_path(cols: int, rows: int, path: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Order path cells into a walkable route (simple greedy from min cell)."""
    if not path:
        return [(0, 0)]
    remaining = set(path)
    start = min(remaining, key=lambda p: (p[1], p[0]))
    route = [start]
    remaining.remove(start)
    while remaining:
        cx, cy = route[-1]
        neighbors = [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        nxt = None
        for nb in neighbors:
            if nb in remaining:
                nxt = nb
                break
        if nxt is None:
            nxt = min(remaining, key=lambda p: abs(p[0] - cx) + abs(p[1] - cy))
        route.append(nxt)
        remaining.remove(nxt)
    return route


MAPS: Dict[str, dict] = {
    "classic": {
        "name": "CLASSIC",
        "cols": 12,
        "rows": 11,
        "segments": [("h", 4, 0, 11), ("v", 11, 4, 7), ("h", 7, 0, 11)],
        "desc": "Balanced S-route",
    },
    "zigzag": {
        "name": "ZIGZAG",
        "cols": 14,
        "rows": 12,
        "segments": [
            ("h", 2, 0, 13),
            ("v", 13, 2, 5),
            ("h", 5, 0, 13),
            ("v", 0, 5, 8),
            ("h", 8, 0, 13),
        ],
        "desc": "Long zigzag path",
    },
    "spiral": {
        "name": "ARENA",
        "cols": 14,
        "rows": 10,
        "segments": [
            ("h", 4, 1, 12),
            ("v", 12, 4, 7),
            ("h", 7, 2, 11),
            ("v", 2, 5, 7),
            ("h", 5, 2, 10),
        ],
        "desc": "Wide arena loops",
    },
    "fortress": {
        "name": "FORTRESS",
        "cols": 12,
        "rows": 14,
        "segments": [
            ("h", 3, 0, 11),
            ("v", 11, 3, 10),
            ("h", 10, 0, 11),
            ("v", 0, 7, 10),
            ("h", 7, 0, 5),
        ],
        "desc": "Tall fortress run",
    },
    "gauntlet": {
        "name": "GAUNTLET",
        "cols": 10,
        "rows": 14,
        "segments": [
            ("v", 1, 0, 13),
            ("h", 13, 1, 8),
            ("v", 8, 10, 13),
            ("h", 10, 2, 8),
            ("v", 2, 3, 10),
        ],
        "desc": "Tight vertical gauntlet",
    },
}


@dataclass
class MapLayout:
    map_id: str
    cols: int
    rows: int
    cell: int
    ox: int
    oy: int
    path_cells: Set[Tuple[int, int]]
    path_px: List[Tuple[float, float]]
    path_cum: List[float]
    path_total: float

    def cell_at(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        if y < HUD_H + ACTION_H + 4 or y >= LOG_H - BAR_H - 4:
            return None
        gx = (x - self.ox) // self.cell
        gy = (y - self.oy) // self.cell
        if 0 <= gx < self.cols and 0 <= gy < self.rows:
            return gx, gy
        return None

    def grid_to_px(self, gx: int, gy: int) -> Tuple[float, float]:
        return self.ox + gx * self.cell + self.cell / 2, self.oy + gy * self.cell + self.cell / 2


def build_map_layout(map_id: str) -> MapLayout:
    spec = MAPS[map_id]
    cols, rows = spec["cols"], spec["rows"]
    path_cells = _path_from_segments(cols, rows, spec["segments"])
    cell = min((LOG_W - 24) // cols, (LOG_H - HUD_H - ACTION_H - BAR_H - 20) // rows)
    cell = max(28, min(cell, 42))
    grid_w = cols * cell
    grid_h = rows * cell
    ox = (LOG_W - grid_w) // 2
    oy = HUD_H + ACTION_H + (LOG_H - HUD_H - ACTION_H - BAR_H - grid_h) // 2
    wps = _waypoints_from_path(cols, rows, path_cells)
    path_px = [((ox + gx * cell + cell / 2), (oy + gy * cell + cell / 2)) for gx, gy in wps]
    cum = [0.0]
    for i in range(1, len(path_px)):
        cum.append(cum[-1] + math.hypot(path_px[i][0] - path_px[i - 1][0], path_px[i][1] - path_px[i - 1][1]))
    total = cum[-1] if cum else 1.0
    return MapLayout(map_id, cols, rows, cell, ox, oy, path_cells, path_px, cum, total)


def pos_on_path(layout: MapLayout, t: float) -> Tuple[float, float]:
    t = max(0.0, min(layout.path_total, t))
    for i in range(len(layout.path_cum) - 1):
        if t <= layout.path_cum[i + 1]:
            seg = layout.path_cum[i + 1] - layout.path_cum[i]
            u = 0 if seg < 0.001 else (t - layout.path_cum[i]) / seg
            x = layout.path_px[i][0] + (layout.path_px[i + 1][0] - layout.path_px[i][0]) * u
            y = layout.path_px[i][1] + (layout.path_px[i + 1][1] - layout.path_px[i][1]) * u
            return x, y
    return layout.path_px[-1]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower().replace(" ", "") in ("griddefense",):
        parent = os.path.dirname(d)
        if os.path.basename(parent).lower() == "portablegames":
            return os.path.dirname(parent)
    return None


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
        self.sfx_on = True
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.shoot = _tone(620, 30, 0.18)
            self.hit = _tone(200, 50, 0.2)
            self.build = _tone(440, 50, 0.2)
            self.wave = _tone(520, 80, 0.22)
            self.life = _tone(120, 140, 0.3)
            self.ui = _tone(520, 40, 0.2)
            self.unlock = _tone(880, 60, 0.22)
        except pygame.error:
            self.enabled = False

    def play(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and self.sfx_on and snd:
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


def load_stats() -> dict:
    data = load_json(STATS_PATH, {"best_wave": 0, "games_played": 0, "unlocked": {}})
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            data["best_wave"] = max(int(data.get("best_wave", 0)), int(g.get("best_wave", 0)))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


def save_stats(data: dict) -> None:
    save_json(STATS_PATH, data)
    prof = profile_path()
    if not prof:
        return
    root = load_json(prof, {"profile": "default", "games": {}})
    root.setdefault("games", {})[GAME_ID] = data
    save_json(prof, root)



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


@dataclass
class Enemy:
    path_t: float
    speed: float
    hp: int
    max_hp: int
    reward: int
    slow: float = 1.0

    def pos(self, layout: MapLayout) -> Tuple[float, float]:
        return pos_on_path(layout, self.path_t)


@dataclass
class Tower:
    gx: int
    gy: int
    kind: str
    level: int = 1
    invested: int = 0
    cooldown: float = 0.0


@dataclass
class Projectile:
    x: float
    y: float
    tx: float
    ty: float
    speed: float
    damage: int
    target_id: int
    splash: float = 0.0
    slow: float = 1.0


class Screen(Enum):
    TITLE = auto()
    MAP_SELECT = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class GridDefenseGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Grid Defense — UsbGames")
        self._display = pygame.display.set_mode((LOG_W, LOG_H))
        self.canvas = pygame.Surface((LOG_W, LOG_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 28, bold=True)
        self.font_md = pygame.font.SysFont("courier", 20, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 15)
        self.font_xs = pygame.font.SysFont("courier", 12)

        self.audio = Audio()
        self.stats = load_stats()
        self.screen_id = Screen.TITLE
        self.map_id = "classic"
        self.layout = build_map_layout(self.map_id)
        self.gold = 150
        self.lives = 12
        self.wave = 0
        self.selected_tower = "blaster"
        self.action_mode = "place"
        self.tower_scroll = 0
        self._hover_cell: Optional[Tuple[int, int]] = None
        self.enemies: List[Enemy] = []
        self.towers: List[Tower] = []
        self.projectiles: List[Projectile] = []
        self._spawn_left = 0
        self._spawn_timer = 0.0
        self._wave_break = 0.0
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._new_unlocks: List[str] = []

    def _map_mouse(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        return pos

    def _present(self) -> None:
        self._display.blit(self.canvas, (0, 0))
        pygame.display.flip()

    def _pixel_text(self, text: str, x: int, y: int, font: pygame.font.Font, color: Tuple[int, int, int], center: bool = False) -> None:
        surf = font.render(text, True, color)
        rx = x - surf.get_width() // 2 if center else x
        self.canvas.blit(surf, (rx, y))

    def _tower_unlocked(self, kind: str) -> bool:
        return self.wave >= TOWER_TYPES[kind]["unlock"]

    def _tower_at(self, gx: int, gy: int) -> Optional[Tower]:
        for t in self.towers:
            if t.gx == gx and t.gy == gy:
                return t
        return None

    def _tower_stats(self, tower: Tower) -> dict:
        base = TOWER_TYPES[tower.kind]
        lv = tower.level
        dmg_mult = 1.0 + (lv - 1) * 0.4
        rng_mult = 1.0 + (lv - 1) * 0.12
        cd_mult = max(0.55, 1.0 - (lv - 1) * 0.15)
        return {
            "range": base["range"] * rng_mult * self.layout.cell,
            "damage": max(1, int(base["damage"] * dmg_mult)),
            "cooldown": base["cooldown"] * cd_mult,
            "splash": base.get("splash", 0),
            "slow": base.get("slow", 1.0),
        }

    def _upgrade_cost(self, tower: Tower) -> int:
        if tower.level >= MAX_TOWER_LEVEL:
            return 0
        base = TOWER_TYPES[tower.kind]["cost"]
        return max(15, int(base * UPGRADE_COST_FACTOR * tower.level))

    def _try_place_tower(self, gx: int, gy: int) -> None:
        if (gx, gy) in self.layout.path_cells:
            return
        if self._tower_at(gx, gy):
            return
        if not self._tower_unlocked(self.selected_tower):
            return
        spec = TOWER_TYPES[self.selected_tower]
        cost = spec["cost"]
        if self.gold < cost:
            return
        self.gold -= cost
        self.towers.append(Tower(gx, gy, self.selected_tower, level=1, invested=cost))
        self.audio.play(self.audio.build)

    def _try_upgrade_tower(self, tower: Tower) -> None:
        if tower.level >= MAX_TOWER_LEVEL:
            return
        cost = self._upgrade_cost(tower)
        if cost <= 0 or self.gold < cost:
            return
        self.gold -= cost
        tower.invested += cost
        tower.level += 1
        tower.cooldown = 0.0
        self.audio.play(self.audio.unlock)

    def _try_sell_tower(self, tower: Tower) -> None:
        refund = max(1, int(tower.invested * SELL_REFUND_RATE))
        self.gold += refund
        self.towers.remove(tower)
        self.audio.play(self.audio.ui)

    def _handle_grid_click(self, gx: int, gy: int) -> None:
        tower = self._tower_at(gx, gy)
        if self.action_mode == "place":
            if tower is None:
                self._try_place_tower(gx, gy)
        elif self.action_mode == "upgrade":
            if tower:
                self._try_upgrade_tower(tower)
        elif self.action_mode == "sell":
            if tower:
                self._try_sell_tower(tower)

    def start_game(self, map_id: Optional[str] = None) -> None:
        if map_id:
            self.map_id = map_id
        self.layout = build_map_layout(self.map_id)
        self.gold = 150
        self.lives = 12
        self.wave = 0
        self.towers.clear()
        self.enemies.clear()
        self.projectiles.clear()
        self._spawn_left = 0
        self._wave_break = 1.2
        self.screen_id = Screen.PLAYING
        st = load_stats()
        st["games_played"] = int(st.get("games_played", 0)) + 1
        save_stats(st)
        self.stats = load_stats()

    def _start_wave(self) -> None:
        self.wave += 1
        self._spawn_left = 5 + self.wave * 2
        self._spawn_timer = 0.35
        self.audio.play(self.audio.wave)
        for kind in TOWER_ORDER:
            spec = TOWER_TYPES[kind]
            if spec["unlock"] == self.wave and kind not in self._new_unlocks:
                self._new_unlocks.append(kind)
                self.audio.play(self.audio.unlock)

    def _spawn_enemy(self) -> None:
        hp = 2 + self.wave + self.wave // 2
        spd = 50 + self.wave * 5
        self.enemies.append(Enemy(0.0, spd, hp, hp, 6 + self.wave))

    def _game_over(self) -> None:
        self.screen_id = Screen.GAME_OVER
        st = load_stats()
        if self.wave > int(st.get("best_wave", 0)):
            st["best_wave"] = self.wave
        save_stats(st)
        self.stats = load_stats()

    def _tower_fire(self, tower: Tower, dt: float) -> None:
        stats = self._tower_stats(tower)
        tower.cooldown -= dt
        if tower.cooldown > 0:
            return
        tx, ty = self.layout.grid_to_px(tower.gx, tower.gy)
        rng = stats["range"]
        best: Optional[Enemy] = None
        best_d = rng + 1
        for e in self.enemies:
            ex, ey = e.pos(self.layout)
            d = math.hypot(ex - tx, ey - ty)
            if d <= rng and d < best_d:
                best_d, best = d, e
        if not best:
            return
        tower.cooldown = stats["cooldown"]
        self.audio.play(self.audio.shoot)
        ex, ey = best.pos(self.layout)
        self.projectiles.append(
            Projectile(
                tx, ty, ex, ey, 340.0, stats["damage"], id(best),
                splash=float(stats.get("splash", 0)),
                slow=float(stats.get("slow", 1.0)),
            )
        )

    def update(self, dt: float) -> None:
        if self.screen_id != Screen.PLAYING:
            return
        if self._wave_break > 0:
            self._wave_break -= dt
            if self._wave_break <= 0:
                self._start_wave()
            return

        if self._spawn_left > 0:
            self._spawn_timer -= dt
            if self._spawn_timer <= 0:
                self._spawn_enemy()
                self._spawn_left -= 1
                self._spawn_timer = max(0.2, 0.65 - self.wave * 0.025)

        for e in list(self.enemies):
            spd = e.speed * e.slow
            e.path_t += spd * dt
            e.slow = min(1.0, e.slow + (1.0 - e.slow) * dt * 2)
            if e.path_t >= self.layout.path_total:
                self.enemies.remove(e)
                self.lives -= 1
                self.audio.play(self.audio.life)
                if self.lives <= 0:
                    self._game_over()

        for t in self.towers:
            self._tower_fire(t, dt)

        for p in list(self.projectiles):
            dx, dy = p.tx - p.x, p.ty - p.y
            dist = math.hypot(dx, dy)
            if dist < 10:
                hit_x, hit_y = p.x, p.y
                for e in list(self.enemies):
                    ex, ey = e.pos(self.layout)
                    if math.hypot(ex - hit_x, ey - hit_y) <= max(18, p.splash):
                        e.hp -= p.damage
                        e.slow = min(e.slow, p.slow)
                        if e.hp <= 0:
                            self.gold += e.reward
                            self.enemies.remove(e)
                self.audio.play(self.audio.hit)
                if p in self.projectiles:
                    self.projectiles.remove(p)
                continue
            step = p.speed * dt
            p.x += dx / dist * step
            p.y += dy / dist * step

        if self._spawn_left <= 0 and not self.enemies:
            self.gold += 20 + self.wave * 6
            self._wave_break = 2.0

    def _draw_grid(self) -> None:
        L = self.layout
        for gy in range(L.rows):
            for gx in range(L.cols):
                r = pygame.Rect(L.ox + gx * L.cell, L.oy + gy * L.cell, L.cell, L.cell)
                if (gx, gy) in L.path_cells:
                    pygame.draw.rect(self.canvas, COL_PATH, r)
                    pygame.draw.rect(self.canvas, COL_PATH_EDGE, r, 1)
                else:
                    pygame.draw.rect(self.canvas, COL_GRID, r)
                    inner = r.inflate(-4, -4)
                    pygame.draw.rect(self.canvas, (22, 28, 38), inner)
                    pygame.draw.rect(self.canvas, (30, 38, 50), inner, 1)

    def _draw_towers(self) -> None:
        for t in self.towers:
            spec = TOWER_TYPES[t.kind]
            cx, cy = map(int, self.layout.grid_to_px(t.gx, t.gy))
            s = max(8, self.layout.cell // 3)
            pygame.draw.rect(self.canvas, spec["color"], (cx - s, cy - s, s * 2, s * 2), border_radius=3)
            pygame.draw.rect(self.canvas, COL_TEXT, (cx - s, cy - s, s * 2, s * 2), 1, border_radius=3)
            if t.level > 1:
                self._pixel_text(str(t.level), cx, cy - 4, self.font_xs, (255, 255, 255), center=True)
            if self._hover_cell == (t.gx, t.gy) and self.action_mode in ("upgrade", "sell"):
                ring = COL_GREEN if self.action_mode == "upgrade" else COL_RED
                pygame.draw.rect(self.canvas, ring, (cx - s - 3, cy - s - 3, s * 2 + 6, s * 2 + 6), 2, border_radius=4)

    def _draw_enemies(self) -> None:
        for e in self.enemies:
            x, y = map(int, e.pos(self.layout))
            pygame.draw.rect(self.canvas, COL_RED, (x - 9, y - 7, 18, 14), border_radius=2)
            w = 20
            pct = e.hp / max(1, e.max_hp)
            pygame.draw.rect(self.canvas, (40, 40, 50), (x - w // 2, y - 14, w, 3))
            pygame.draw.rect(self.canvas, COL_GREEN, (x - w // 2, y - 14, int(w * pct), 3))

    def _draw_action_bar(self) -> None:
        y = LOG_H - BAR_H - ACTION_H
        pygame.draw.rect(self.canvas, (6, 8, 14), (0, y, LOG_W, ACTION_H))
        modes = [("place", "BUILD"), ("upgrade", "UPGRADE"), ("sell", "SELL")]
        bw = 100
        x = LOG_W // 2 - (bw * 3 + 16) // 2
        for mode, label in modes:
            r = pygame.Rect(x, y + 4, bw, ACTION_H - 8)
            sel = self.action_mode == mode
            pygame.draw.rect(self.canvas, COL_BTN_HOVER if sel else COL_BTN, r, border_radius=4)
            col = COL_TURQ if mode == "place" else (COL_GREEN if mode == "upgrade" else COL_RED)
            pygame.draw.rect(self.canvas, col if sel else COL_DIM, r, 2, border_radius=4)
            self._pixel_text(label, r.centerx, r.centery - 6, self.font_xs, COL_TEXT, center=True)
            x += bw + 8
    def _action_bar_hit(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        bar_top = LOG_H - BAR_H - ACTION_H
        if y < bar_top or y >= LOG_H - BAR_H:
            return False
        bw = 100
        bx = LOG_W // 2 - (bw * 3 + 16) // 2
        for mode, _ in [("place", "BUILD"), ("upgrade", "UPGRADE"), ("sell", "SELL")]:
            r = pygame.Rect(bx, bar_top + 4, bw, ACTION_H - 8)
            if r.collidepoint(x, y):
                self.action_mode = mode
                self.audio.play(self.audio.ui)
                return True
            bx += bw + 8
        return False

    def _draw_tower_bar(self) -> None:
        bar_y = LOG_H - BAR_H
        pygame.draw.rect(self.canvas, (6, 8, 14), (0, bar_y, LOG_W, BAR_H))
        slot_w = 76
        x0 = 8 - self.tower_scroll
        for i, key in enumerate(TOWER_ORDER):
            spec = TOWER_TYPES[key]
            rx = x0 + i * slot_w
            if rx + slot_w < 0 or rx > LOG_W:
                continue
            r = pygame.Rect(rx, bar_y + 8, slot_w - 6, BAR_H - 16)
            unlocked = self._tower_unlocked(key)
            sel = key == self.selected_tower
            bg = COL_BTN_HOVER if sel else COL_BTN
            if not unlocked:
                bg = COL_LOCKED
            pygame.draw.rect(self.canvas, bg, r, border_radius=4)
            border = spec["color"] if sel and unlocked else COL_DIM
            pygame.draw.rect(self.canvas, border, r, 2, border_radius=4)
            name = spec["name"][:6]
            self._pixel_text(name, r.centerx, r.y + 4, self.font_xs, COL_TEXT if unlocked else COL_DIM, center=True)
            cost_txt = f"${spec['cost']}" if unlocked else f"W{spec['unlock']}"
            self._pixel_text(cost_txt, r.centerx, r.y + 20, self.font_xs, COL_ORANGE if unlocked else COL_RED, center=True)
            if not unlocked:
                self._pixel_text("LOCK", r.centerx, r.centery + 10, self.font_xs, COL_DIM, center=True)

    def _tower_bar_hit(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if y < LOG_H - BAR_H:
            return False
        slot_w = 76
        x0 = 8 - self.tower_scroll
        for i, key in enumerate(TOWER_ORDER):
            rx = x0 + i * slot_w
            r = pygame.Rect(rx, LOG_H - BAR_H + 8, slot_w - 6, BAR_H - 16)
            if r.collidepoint(x, y):
                if self._tower_unlocked(key):
                    self.selected_tower = key
                    self.audio.play(self.audio.ui)
                return True
        return False

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.canvas, (6, 8, 14), (0, 0, LOG_W, HUD_H))
        self._pixel_text(f"GOLD {self.gold}", 8, 10, self.font_sm, COL_ORANGE)
        self._pixel_text(f"WAVE {self.wave}", LOG_W // 2, 10, self.font_sm, COL_TURQ, center=True)
        self._pixel_text(MAPS[self.map_id]["name"], LOG_W // 2, 28, self.font_xs, COL_DIM, center=True)
        surf = self.font_sm.render(f"LIVES {self.lives}", True, COL_RED)
        self.canvas.blit(surf, (LOG_W - surf.get_width() - 8, 10))

    def _make_btn(self, y: int, label: str, action: str, w: int = 220) -> None:
        self._buttons.append((pygame.Rect(LOG_W // 2 - w // 2, y, w, 34), label, action))

    def _draw_buttons(self) -> None:
        for rect, label, action in self._buttons:
            hov = self._hover == action
            pygame.draw.rect(self.canvas, COL_BTN_HOVER if hov else COL_BTN, rect)
            pygame.draw.rect(self.canvas, COL_TURQ if hov else COL_DIM, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 7, self.font_md, COL_TEXT, center=True)

    def draw(self) -> None:
        self.canvas.fill(COL_BG)
        self._buttons.clear()
        if self.screen_id == Screen.TITLE:
            self._draw_title()
        elif self.screen_id == Screen.MAP_SELECT:
            self._draw_map_select()
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED):
            self._draw_play()
            if self.screen_id == Screen.PAUSED:
                o = pygame.Surface((LOG_W, LOG_H), pygame.SRCALPHA)
                o.fill((0, 0, 0, 160))
                self.canvas.blit(o, (0, 0))
                self._pixel_text("PAUSED", LOG_W // 2, LOG_H // 2, self.font_lg, COL_TURQ, center=True)
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_play()
            o = pygame.Surface((LOG_W, LOG_H), pygame.SRCALPHA)
            o.fill((0, 0, 0, 175))
            self.canvas.blit(o, (0, 0))
            self._pixel_text("DEFEAT", LOG_W // 2, 140, self.font_lg, COL_RED, center=True)
            self._pixel_text(f"WAVE {self.wave}", LOG_W // 2, 190, self.font_md, COL_TEXT, center=True)
            self._make_btn(320, "RETRY", "retry")
            self._make_btn(368, "MAPS", "maps")
            self._make_btn(416, "MENU", "title")
            self._draw_buttons()
        self._present()

    def _draw_title(self) -> None:
        self._pixel_text("GRID DEFENSE", LOG_W // 2, 100, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames Premium", LOG_W // 2, 135, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"BEST WAVE {self.stats.get('best_wave', 0)}", LOG_W // 2, 168, self.font_md, COL_GREEN, center=True)
        self._make_btn(230, "PLAY", "maps")
        self._draw_buttons()
        self._pixel_text("12 towers unlock as waves progress", LOG_W // 2, 290, self.font_xs, COL_DIM, center=True)
        self._pixel_text("BUILD / UPGRADE / SELL modes · SCROLL TOWERS", LOG_W // 2, 300, self.font_xs, COL_DIM, center=True)
        self._pixel_text("B BUILD · U UPGRADE · X SELL · RIGHT-CLICK SELL", LOG_W // 2, 318, self.font_xs, COL_DIM, center=True)

    def _draw_map_select(self) -> None:
        self._pixel_text("SELECT MAP", LOG_W // 2, 48, self.font_lg, COL_TURQ, center=True)
        y = 100
        for mid in MAPS:
            self._make_btn(y, f"{MAPS[mid]['name']} — {MAPS[mid]['desc']}", f"map:{mid}", 400)
            y += 48
        self._make_btn(y + 10, "BACK", "title", 160)
        self._draw_buttons()

    def _draw_play(self) -> None:
        self._draw_grid()
        self._draw_towers()
        self._draw_enemies()
        for p in self.projectiles:
            pygame.draw.circle(self.canvas, COL_GREEN, (int(p.x), int(p.y)), 4)
        self._draw_hud()
        self._draw_action_bar()
        self._draw_tower_bar()
        if self._hover_cell and self.action_mode == "upgrade":
            t = self._tower_at(self._hover_cell[0], self._hover_cell[1])
            if t and t.level < MAX_TOWER_LEVEL:
                cost = self._upgrade_cost(t)
                self._pixel_text(f"UPGRADE ${cost}", LOG_W // 2, HUD_H + ACTION_H - 6, self.font_xs, COL_GREEN, center=True)
            elif t:
                self._pixel_text("MAX LEVEL", LOG_W // 2, HUD_H + ACTION_H - 6, self.font_xs, COL_ORANGE, center=True)
        elif self._hover_cell and self.action_mode == "sell":
            t = self._tower_at(self._hover_cell[0], self._hover_cell[1])
            if t:
                refund = max(1, int(t.invested * SELL_REFUND_RATE))
                self._pixel_text(f"SELL +${refund}", LOG_W // 2, HUD_H + ACTION_H - 6, self.font_xs, COL_RED, center=True)
        if self._wave_break > 0:
            msg = "GET READY..." if self.wave == 0 else f"WAVE {self.wave + 1}"
            self._pixel_text(msg, LOG_W // 2, self.layout.oy + 20, self.font_md, COL_TURQ, center=True)
        if self._new_unlocks:
            self._pixel_text(f"UNLOCKED: {TOWER_TYPES[self._new_unlocks[-1]]['name']}", LOG_W // 2, HUD_H + 2, self.font_xs, COL_GREEN, center=True)

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "maps":
            self.screen_id = Screen.MAP_SELECT
        elif action == "title":
            self.screen_id = Screen.TITLE
            self._new_unlocks.clear()
        elif action.startswith("map:"):
            self.start_game(action.split(":", 1)[1])
        elif action == "retry":
            self.start_game(self.map_id)
        elif action == "play":
            self.screen_id = Screen.MAP_SELECT

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            mpos = self._map_mouse(event.pos)
            self._hover = self._hit_btn(mpos)
            if self.screen_id == Screen.PLAYING:
                self._hover_cell = self.layout.cell_at(mpos[0], mpos[1])
            else:
                self._hover_cell = None
        if event.type == pygame.MOUSEWHEEL and self.screen_id == Screen.PLAYING:
            self.tower_scroll = max(0, min(self.tower_scroll - event.y * 24, len(TOWER_ORDER) * 76 - LOG_W + 40))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._map_mouse(event.pos)
            act = self._hit_btn(pos)
            if act:
                self._do_action(act)
                return
            if self.screen_id == Screen.TITLE:
                self.screen_id = Screen.MAP_SELECT
                return
            if self.screen_id == Screen.PLAYING:
                if self._action_bar_hit(pos):
                    return
                if self._tower_bar_hit(pos):
                    return
                cell = self.layout.cell_at(pos[0], pos[1])
                if cell:
                    self._handle_grid_click(cell[0], cell[1])
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.screen_id == Screen.PLAYING:
                mpos = self._map_mouse(event.pos)
                cell = self.layout.cell_at(mpos[0], mpos[1])
                if cell:
                    tower = self._tower_at(cell[0], cell[1])
                    if tower:
                        self._try_sell_tower(tower)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.PAUSED
            elif self.screen_id == Screen.PAUSED:
                self.screen_id = Screen.PLAYING
            elif self.screen_id == Screen.MAP_SELECT:
                self.screen_id = Screen.TITLE
            else:
                self.screen_id = Screen.TITLE
        elif self.screen_id == Screen.PLAYING:
            if event.key == pygame.K_b:
                self.action_mode = "place"
                self.audio.play(self.audio.ui)
            elif event.key == pygame.K_u:
                self.action_mode = "upgrade"
                self.audio.play(self.audio.ui)
            elif event.key == pygame.K_x:
                self.action_mode = "sell"
                self.audio.play(self.audio.ui)
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(TOWER_ORDER):
                    self.selected_tower = TOWER_ORDER[idx]
                    self.action_mode = "place"
            elif event.key == pygame.K_0 and len(TOWER_ORDER) > 9:
                self.selected_tower = TOWER_ORDER[9]
                self.action_mode = "place"

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS_CAP) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            if self.screen_id != Screen.PAUSED:
                self.update(dt)
            self.draw()
        pygame.quit()


def main() -> None:
    GridDefenseGame().run()


if __name__ == "__main__":
    main()
