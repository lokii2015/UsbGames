#!/usr/bin/env python3
"""UsbGames Pixel Kart — top-down arcade kart racing."""

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

GAME_ID = "PixelKart"
WIN_W, WIN_H = 480, 640
FPS_CAP = 60
HUD_H = 48
CELL = 20
TOTAL_LAPS = 3
RACE_KARTS = 4

COL_BG = (10, 14, 22)
COL_GRASS = (18, 32, 22)
COL_TRACK = (42, 48, 58)
COL_TRACK_EDGE = (64, 224, 208)
COL_WALL = (28, 34, 48)
COL_TURQ = (64, 224, 208)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_RED = (255, 90, 90)
COL_ORANGE = (255, 160, 60)
COL_YELLOW = (255, 230, 80)

SAMPLE_RATE = 22050

# tile: 0 grass, 1 track, 2 wall, 3 start/finish
KART_TYPES: Dict[str, dict] = {
    "racer": {"name": "RACER", "color": COL_TURQ, "accel": 200, "max_speed": 230, "turn": 3.0, "grip": 0.94},
    "bolt": {"name": "BOLT", "color": COL_ORANGE, "accel": 210, "max_speed": 270, "turn": 2.4, "grip": 0.88},
    "grip": {"name": "GRIP", "color": COL_GREEN, "accel": 185, "max_speed": 215, "turn": 3.6, "grip": 0.97},
}

ITEM_NAMES = {"boost": "BOOST", "shield": "SHIELD", "missile": "MISSILE"}


def _ring_grid(cols: int, rows: int, cx: float, cy: float, inner: float, outer: float) -> List[List[int]]:
    g = [[0] * cols for _ in range(rows)]
    for y in range(rows):
        for x in range(cols):
            dx = (x - cx) / max(cx - 1.5, 1)
            dy = (y - cy) / max(cy - 1.5, 1)
            r2 = dx * dx + dy * dy
            if inner * inner <= r2 <= outer * outer:
                g[y][x] = 1
            elif r2 > outer * outer:
                g[y][x] = 2
    return g


def _rect_track(g: List[List[int]], x0: int, y0: int, x1: int, y1: int, width: int) -> None:
    for y in range(len(g)):
        for x in range(len(g[0])):
            on_h = y0 <= y <= y1 and x0 - width <= x <= x1 + width
            on_v = x0 <= x <= x1 and y0 - width <= y <= y1 + width
            if on_h or on_v:
                if g[y][x] != 2:
                    g[y][x] = 1


def _expand_waypoints(checkpoints: List[Tuple[float, float]], step: float = 2.0) -> List[Tuple[float, float]]:
    """Dense ordered waypoints between gate points for AI steering and lap timing."""
    if not checkpoints:
        return []
    out: List[Tuple[float, float]] = []
    n = len(checkpoints)
    for i in range(n):
        ax, ay = checkpoints[i]
        bx, by = checkpoints[(i + 1) % n]
        seg = math.hypot(bx - ax, by - ay)
        if seg < 0.5:
            continue
        steps = max(2, int(seg / step) + 1)
        for s in range(steps):
            t = s / steps
            px = ax + (bx - ax) * t
            py = ay + (by - ay) * t
            if out and math.hypot(out[-1][0] - px, out[-1][1] - py) < 0.35:
                continue
            out.append((px, py))
    return out


def build_track_grids() -> Dict[str, dict]:
    tracks: Dict[str, dict] = {}

    cols, rows = 28, 28
    g = _ring_grid(cols, rows, 14, 14, 0.42, 0.92)
    g[14][2] = g[14][3] = 3
    gates = [(14, 2), (24, 14), (14, 24), (4, 14)]
    tracks["oval"] = {
        "name": "OVAL",
        "desc": "Smooth banked loop",
        "grid": g,
        "gates": gates,
        "start": (14.0, 4.0),
        "spawns": [(12, 5, 1.57), (14, 5, 1.57), (16, 5, 1.57), (18, 5, 1.57)],
    }

    cols, rows = 30, 26
    g = [[2 if x == 0 or x == cols - 1 or y == 0 or y == rows - 1 else 0 for x in range(cols)] for y in range(rows)]
    _rect_track(g, 2, 10, 27, 14, 2)
    _rect_track(g, 12, 2, 16, 23, 2)
    for y in range(8, 18):
        for x in range(12, 18):
            if g[y][x] != 2:
                g[y][x] = 1
    g[12][3] = 3
    gates = [(26, 12), (14, 3), (3, 12), (14, 22)]
    tracks["circuit"] = {
        "name": "CIRCUIT",
        "desc": "Technical corners",
        "grid": g,
        "gates": gates,
        "start": (5.0, 11.0),
        "spawns": [(5, 11, 0), (7, 11, 0), (9, 11, 0), (11, 11, 0)],
    }

    cols, rows = 32, 22
    g = [[0] * cols for _ in range(rows)]
    for y in range(rows):
        for x in range(cols):
            if y < 3 or y > rows - 4 or x < 2 or x > cols - 3:
                g[y][x] = 2
            elif 4 <= y <= rows - 5:
                g[y][x] = 1
    for x in range(8, 24):
        g[rows // 2][x] = 1
    g[rows // 2][4] = 3
    gates = [(5, 10), (16, 10), (27, 10), (8, 10)]
    tracks["sprint"] = {
        "name": "SPRINT",
        "desc": "Long straights",
        "grid": g,
        "gates": gates,
        "start": (6.0, 9.0),
        "spawns": [(6, 9, 0), (7, 9, 0), (8, 9, 0), (9, 9, 0)],
    }

    gates = [(14, 3), (24, 14), (14, 24), (4, 14)]
    tracks["figure8"] = {
        "name": "FIGURE 8",
        "desc": "Crossover chaos",
        "grid": _figure8_grid(),
        "gates": gates,
        "start": (14.0, 5.0),
        "spawns": [(12, 5, 1.57), (14, 5, 1.57), (16, 5, 1.57), (18, 5, 1.57)],
    }

    for tid in tracks:
        tracks[tid]["waypoints"] = _expand_waypoints(tracks[tid]["gates"], step=1.8)
    return tracks


def _figure8_grid() -> List[List[int]]:
    cols, rows = 28, 28
    g = [[2] * cols for _ in range(rows)]
    for y in range(rows):
        for x in range(cols):
            dx = (x - 14) / 12
            dy = (y - 14) / 12
            d1 = math.hypot(dx + 0.35, dy)
            d2 = math.hypot(dx - 0.35, dy)
            if 0.32 < d1 < 0.78 or 0.32 < d2 < 0.78:
                g[y][x] = 1
            elif abs(dx) < 0.12 and abs(dy) < 0.55:
                g[y][x] = 1
    g[14][3] = 3
    return g


TRACKS = build_track_grids()


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower().replace(" ", "") in ("pixelkart",):
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
            self.engine = _tone(110, 60, 0.08)
            self.boost = _tone(880, 70, 0.25)
            self.bump = _tone(160, 80, 0.22)
            self.item = _tone(660, 50, 0.2)
            self.missile = _tone(240, 90, 0.28)
            self.lap = _tone(520, 80, 0.22)
            self.win = _tone(720, 120, 0.25)
            self.ui = _tone(520, 40, 0.2)
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


def load_stats() -> dict:
    data = load_json(STATS_PATH, {"best_times": {}, "wins": 0, "races": 0})
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            for tid, t in g.get("best_times", {}).items():
                cur = data["best_times"].get(tid)
                if cur is None or t < cur:
                    data["best_times"][tid] = t
            data["wins"] = max(int(data.get("wins", 0)), int(g.get("wins", 0)))
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


class Screen(Enum):
    TITLE = auto()
    TRACK_SELECT = auto()
    KART_SELECT = auto()
    COUNTDOWN = auto()
    RACE = auto()
    RESULTS = auto()
    PAUSED = auto()


@dataclass
class Kart:
    x: float
    y: float
    angle: float
    speed: float = 0.0
    kind: str = "racer"
    is_player: bool = False
    lap: int = 0
    next_wp: int = 0
    finished: bool = False
    finish_time: float = 9999.0
    shield: float = 0.0
    boost: float = 0.0
    spin: float = 0.0
    held_item: Optional[str] = None
    color: Tuple[int, int, int] = COL_TURQ
    ai_skill: float = 0.85
    wp_cooldown: float = 0.0
    left_start: bool = False
    spawn_x: float = 0.0
    spawn_y: float = 0.0

    def spec(self) -> dict:
        return KART_TYPES[self.kind]

    def world_pos(self) -> Tuple[float, float]:
        return self.x * CELL + CELL / 2, self.y * CELL + CELL / 2


@dataclass
class Pickup:
    x: float
    y: float
    kind: str
    ttl: float = 12.0


@dataclass
class Missile:
    x: float
    y: float
    vx: float
    vy: float
    owner: int
    ttl: float = 2.5


class PixelKartGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Pixel Kart — UsbGames")
        self._display = pygame.display.set_mode((WIN_W, WIN_H))
        self.canvas = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 28, bold=True)
        self.font_md = pygame.font.SysFont("courier", 20, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 15)
        self.font_xs = pygame.font.SysFont("courier", 12)

        self.audio = Audio()
        self.stats = load_stats()
        self.screen_id = Screen.TITLE
        self.track_id = "oval"
        self.kart_kind = "racer"
        self.karts: List[Kart] = []
        self.pickups: List[Pickup] = []
        self.missiles: List[Missile] = []
        self.race_time = 0.0
        self.countdown = 0.0
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._result_place = 1
        self._item_cd = 0.0
        self._pickup_spawn = 4.0
        self._cam_x = 0.0
        self._cam_y = 0.0
        self._engine_tick = 0.0

    def _grid(self) -> List[List[int]]:
        return TRACKS[self.track_id]["grid"]

    def _world_size(self) -> Tuple[int, int]:
        g = self._grid()
        return len(g[0]) * CELL, len(g) * CELL

    def _tile_at(self, wx: float, wy: float) -> int:
        g = self._grid()
        tx = int(wx // CELL)
        ty = int(wy // CELL)
        if tx < 0 or ty < 0 or ty >= len(g) or tx >= len(g[0]):
            return 2
        return g[ty][tx]

    def _pixel_text(self, text: str, x: int, y: int, font: pygame.font.Font, color: Tuple[int, int, int], center: bool = False) -> None:
        surf = font.render(text, True, color)
        rx = x - surf.get_width() // 2 if center else x
        self.canvas.blit(surf, (rx, y))

    def _make_btn(self, y: int, label: str, action: str, w: int = 280) -> None:
        r = pygame.Rect((WIN_W - w) // 2, y, w, 36)
        hover = self._hover == action
        pygame.draw.rect(self.canvas, COL_BTN_HOVER if hover else COL_BTN, r, border_radius=4)
        pygame.draw.rect(self.canvas, COL_TURQ if hover else COL_DIM, r, 2, border_radius=4)
        self._pixel_text(label, r.centerx, r.centery - 8, self.font_sm, COL_TEXT, center=True)
        self._buttons.append((r, label, action))

    def _draw_buttons(self) -> None:
        pass

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _start_race(self) -> None:
        track = TRACKS[self.track_id]
        spawns = track["spawns"]
        colors = [KART_TYPES[self.kart_kind]["color"], COL_RED, COL_ORANGE, (180, 120, 255)]
        kinds = [self.kart_kind, "bolt", "grip", "racer"]
        self.karts = []
        for i in range(RACE_KARTS):
            sx, sy, ang = spawns[i]
            k = Kart(
                float(sx),
                float(sy),
                ang,
                kind=kinds[i],
                is_player=(i == 0),
                color=colors[i],
                ai_skill=0.78 + i * 0.05,
                spawn_x=float(sx),
                spawn_y=float(sy),
            )
            self.karts.append(k)
        self.pickups.clear()
        self.missiles.clear()
        self.race_time = 0.0
        self.countdown = 3.2
        self._item_cd = 0.0
        self._pickup_spawn = 3.0
        self.screen_id = Screen.COUNTDOWN
        st = load_stats()
        st["races"] = int(st.get("races", 0)) + 1
        save_stats(st)
        self.stats = load_stats()

    def _waypoints(self) -> List[Tuple[float, float]]:
        return TRACKS[self.track_id]["waypoints"]

    def _race_progress(self, k: Kart) -> float:
        wps = self._waypoints()
        if not wps:
            return 0.0
        n = len(wps)
        tx, ty = wps[k.next_wp % n]
        dist = math.hypot(k.x - tx, k.y - ty)
        frac = max(0.0, 1.0 - dist / 3.5)
        if k.finished:
            return k.lap * n + n + k.finish_time * 0.001
        return k.lap * n + k.next_wp + frac

    def _rank(self) -> List[int]:
        def sort_key(i: int) -> Tuple[int, float, float]:
            k = self.karts[i]
            if k.finished:
                return (0, k.finish_time, -self._race_progress(k))
            return (1, 0.0, -self._race_progress(k))

        return sorted(range(len(self.karts)), key=sort_key)

    def _player_rank(self) -> int:
        for i, idx in enumerate(self._rank()):
            if self.karts[idx].is_player:
                return i + 1
        return RACE_KARTS

    def _advance_checkpoint(self, k: Kart) -> None:
        if k.finished or k.wp_cooldown > 0:
            return

        wps = self._waypoints()
        if not wps:
            return

        if not k.left_start:
            if math.hypot(k.x - k.spawn_x, k.y - k.spawn_y) > 2.2:
                k.left_start = True
            return

        tx, ty = wps[k.next_wp % len(wps)]
        if math.hypot(k.x - tx, k.y - ty) > 1.35:
            return

        k.next_wp += 1
        k.wp_cooldown = 0.45
        n = len(wps)

        if k.next_wp >= n:
            k.next_wp = 0
            k.lap += 1
            if k.is_player:
                self.audio.play(self.audio.lap)
            if k.lap >= TOTAL_LAPS:
                k.finished = True
                k.finish_time = self.race_time

    def _collide_walls(self, k: Kart, nx: float, ny: float) -> Tuple[float, float]:
        wx, wy = nx * CELL + CELL / 2, ny * CELL + CELL / 2
        r = CELL * 0.32
        for ox, oy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
            if self._tile_at(wx + ox, wy + oy) == 2:
                return k.x, k.y
        return nx, ny

    def _surface_mul(self, k: Kart) -> float:
        wx, wy = k.world_pos()
        t = self._tile_at(wx, wy)
        if t == 1:
            return 1.0
        if t == 3:
            return 1.05
        return 0.55

    def _update_kart(self, k: Kart, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        spec = k.spec()
        if k.spin > 0:
            k.spin = max(0.0, k.spin - dt)
            k.speed *= 0.96
        elif k.finished:
            k.speed *= 0.9
        else:
            accel = 0.0
            turn = 0.0
            if k.is_player:
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    accel = 1.0
                if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    accel = -0.65
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    turn = 1.0
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    turn = -1.0
            else:
                accel, turn = self._ai_steer(k)

            speed_factor = min(1.0, abs(k.speed) / max(spec["max_speed"], 1))
            if turn:
                k.angle += turn * spec["turn"] * dt * (0.45 + 0.55 * speed_factor)
            if accel > 0:
                boost = 1.65 if k.boost > 0 else 1.0
                k.speed += accel * spec["accel"] * boost * self._surface_mul(k) * dt
            elif accel < 0:
                k.speed -= spec["accel"] * 0.9 * dt
            else:
                k.speed *= spec["grip"] ** (dt * 60)

            max_s = spec["max_speed"] * (1.35 if k.boost > 0 else 1.0)
            k.speed = max(-max_s * 0.35, min(max_s, k.speed))

        k.boost = max(0.0, k.boost - dt)
        k.shield = max(0.0, k.shield - dt)
        k.wp_cooldown = max(0.0, k.wp_cooldown - dt)

        vx = math.cos(k.angle) * k.speed * dt
        vy = math.sin(k.angle) * k.speed * dt
        nx, ny = self._collide_walls(k, k.x + vx / CELL, k.y + vy / CELL)
        k.x, k.y = nx, ny
        if not k.finished:
            self._advance_checkpoint(k)

        if abs(k.speed) > 40 and random.random() < dt * 2.5:
            self._engine_tick += dt
            if self._engine_tick > 0.12:
                self._engine_tick = 0.0
                if k.is_player:
                    self.audio.play(self.audio.engine)

    def _ai_target_wp(self, k: Kart) -> Tuple[float, float]:
        wps = self._waypoints()
        if not wps:
            return k.x, k.y
        lookahead = 3 + int(min(abs(k.speed), 220) / 70)
        idx = (k.next_wp + lookahead) % len(wps)
        return wps[idx]

    def _ai_steer(self, k: Kart) -> Tuple[float, float]:
        tx, ty = self._ai_target_wp(k)
        dx, dy = tx - k.x, ty - k.y
        if math.hypot(dx, dy) < 0.15:
            tx, ty = self._waypoints()[(k.next_wp + 1) % len(self._waypoints())]
            dx, dy = tx - k.x, ty - k.y

        target = math.atan2(dy, dx)
        diff = (target - k.angle + math.pi) % (2 * math.pi) - math.pi
        steer = max(-1.0, min(1.0, diff * 2.4 * k.ai_skill))

        wx, wy = k.world_pos()
        ahead = k.angle
        for side, sign in ((-0.45, 1.0), (0.45, -1.0)):
            px = wx + math.cos(ahead + side) * 26
            py = wy + math.sin(ahead + side) * 26
            if self._tile_at(px, py) == 2:
                steer += sign * 0.55
        steer = max(-1.0, min(1.0, steer))

        tile = self._tile_at(wx, wy)
        on_track = tile in (1, 3)
        if not on_track:
            steer *= 1.25

        if abs(diff) < 0.55:
            accel = 1.0
        elif abs(diff) < 1.2:
            accel = 0.75
        else:
            accel = 0.45
        if not on_track:
            accel = min(1.0, accel + 0.2)
        if self._tile_at(wx + math.cos(ahead) * 22, wy + math.sin(ahead) * 22) == 2:
            accel = min(accel, 0.35)

        return accel, steer

    def _spawn_pickup(self) -> None:
        g = self._grid()
        opts: List[Tuple[float, float]] = []
        for y in range(len(g)):
            for x in range(len(g[0])):
                if g[y][x] == 1 and random.random() < 0.02:
                    opts.append((float(x) + 0.5, float(y) + 0.5))
        if not opts:
            return
        px, py = random.choice(opts)
        kind = random.choice(["boost", "shield", "missile"])
        self.pickups.append(Pickup(px, py, kind))

    def _use_item(self, k: Kart) -> None:
        if not k.held_item or k.finished:
            return
        item = k.held_item
        k.held_item = None
        self.audio.play(self.audio.item)
        if item == "boost":
            k.boost = 2.2
            self.audio.play(self.audio.boost)
        elif item == "shield":
            k.shield = 4.0
        elif item == "missile":
            wx, wy = k.world_pos()
            ang = k.angle
            self.missiles.append(Missile(wx, wy, math.cos(ang) * 320, math.sin(ang) * 320, self.karts.index(k)))
            self.audio.play(self.audio.missile)

    def _update_missiles(self, dt: float) -> None:
        for m in self.missiles[:]:
            m.ttl -= dt
            m.x += m.vx * dt
            m.y += m.vy * dt
            if m.ttl <= 0 or self._tile_at(m.x, m.y) == 2:
                self.missiles.remove(m)
                continue
            for i, k in enumerate(self.karts):
                if i == m.owner or k.finished:
                    continue
                wx, wy = k.world_pos()
                if math.hypot(m.x - wx, m.y - wy) < CELL * 0.55:
                    self.missiles.remove(m)
                    if k.shield > 0:
                        k.shield = 0.0
                    else:
                        k.spin = 1.2
                        k.speed *= 0.3
                        self.audio.play(self.audio.bump)
                    break

    def _check_pickups(self, k: Kart) -> None:
        for p in self.pickups[:]:
            if math.hypot(k.x - p.x, k.y - p.y) < 0.9:
                if k.is_player and not k.held_item:
                    k.held_item = p.kind
                elif not k.is_player and random.random() < 0.35:
                    if p.kind == "boost":
                        k.boost = 2.0
                    elif p.kind == "shield":
                        k.shield = 3.0
                self.pickups.remove(p)
                if k.is_player:
                    self.audio.play(self.audio.item)

    def _check_kart_bumps(self) -> None:
        for i in range(len(self.karts)):
            for j in range(i + 1, len(self.karts)):
                a, b = self.karts[i], self.karts[j]
                d = math.hypot(a.x - b.x, a.y - b.y)
                if d < 0.85 and d > 0.01:
                    push = (0.85 - d) * 0.5
                    ang = math.atan2(b.y - a.y, b.x - a.x)
                    a.x -= math.cos(ang) * push
                    a.y -= math.sin(ang) * push
                    b.x += math.cos(ang) * push
                    b.y += math.sin(ang) * push
                    a.speed *= 0.92
                    b.speed *= 0.92

    def update(self, dt: float) -> None:
        if self.screen_id == Screen.COUNTDOWN:
            self.countdown -= dt
            if self.countdown <= 0:
                self.screen_id = Screen.RACE
            return
        if self.screen_id != Screen.RACE:
            return

        self.race_time += dt
        keys = pygame.key.get_pressed()
        for k in self.karts:
            self._update_kart(k, dt, keys)

        self._check_kart_bumps()
        for k in self.karts:
            self._check_pickups(k)

        self._pickup_spawn -= dt
        if self._pickup_spawn <= 0:
            self._pickup_spawn = 5.0 + random.random() * 3.0
            self._spawn_pickup()

        self._item_cd -= dt
        if keys[pygame.K_SPACE] and self._item_cd <= 0:
            self._use_item(self.karts[0])
            self._item_cd = 0.35

        self._update_missiles(dt)

        finished = sum(1 for k in self.karts if k.finished)
        if finished >= RACE_KARTS or (self.karts[0].finished and self.race_time > self.karts[0].finish_time + 2.5):
            self._result_place = self._player_rank()
            if self._result_place == 1:
                st = load_stats()
                st["wins"] = int(st.get("wins", 0)) + 1
                tid = self.track_id
                best = st.setdefault("best_times", {})
                prev = best.get(tid)
                t = self.karts[0].finish_time
                if prev is None or t < prev:
                    best[tid] = round(t, 2)
                save_stats(st)
                self.stats = load_stats()
                self.audio.play(self.audio.win)
            self.screen_id = Screen.RESULTS

    def _update_camera(self) -> None:
        p = self.karts[0]
        wx, wy = p.world_pos()
        ww, wh = self._world_size()
        view_w, view_h = WIN_W, WIN_H - HUD_H
        self._cam_x = max(0, min(wx - view_w / 2, ww - view_w))
        self._cam_y = max(0, min(wy - view_h / 2, wh - view_h))

    def _draw_track(self) -> None:
        g = self._grid()
        view = pygame.Rect(int(self._cam_x), int(self._cam_y), WIN_W, WIN_H - HUD_H)
        x0 = max(0, view.left // CELL - 1)
        y0 = max(0, view.top // CELL - 1)
        x1 = min(len(g[0]), view.right // CELL + 2)
        y1 = min(len(g), view.bottom // CELL + 2)
        for y in range(y0, y1):
            for x in range(x0, x1):
                t = g[y][x]
                rx = x * CELL - self._cam_x
                ry = y * CELL - self._cam_y + HUD_H
                if t == 2:
                    col = COL_WALL
                elif t == 1:
                    col = COL_TRACK
                elif t == 3:
                    col = COL_YELLOW
                else:
                    col = COL_GRASS
                pygame.draw.rect(self.canvas, col, (rx, ry, CELL, CELL))
                if t == 1:
                    pygame.draw.rect(self.canvas, COL_TRACK_EDGE, (rx, ry, CELL, CELL), 1)

    def _draw_kart(self, k: Kart) -> None:
        wx, wy = k.world_pos()
        sx = wx - self._cam_x
        sy = wy - self._cam_y + HUD_H
        if sx < -40 or sy < -40 or sx > WIN_W + 40 or sy > WIN_H + 40:
            return
        pts = []
        for ox, oy in ((14, 0), (-10, 8), (-10, -8)):
            px = sx + ox * math.cos(k.angle) - oy * math.sin(k.angle)
            py = sy + ox * math.sin(k.angle) + oy * math.cos(k.angle)
            pts.append((px, py))
        pygame.draw.polygon(self.canvas, k.color, pts)
        pygame.draw.polygon(self.canvas, COL_TEXT, pts, 1)
        if k.shield > 0:
            pygame.draw.circle(self.canvas, COL_TURQ, (int(sx), int(sy)), 16, 2)
        if k.held_item and k.is_player:
            self._pixel_text("!", int(sx), int(sy) - 22, self.font_xs, COL_YELLOW, center=True)

    def _draw_pickups(self) -> None:
        for p in self.pickups:
            wx, wy = p.x * CELL + CELL / 2, p.y * CELL + CELL / 2
            sx = wx - self._cam_x
            sy = wy - self._cam_y + HUD_H
            col = COL_ORANGE if p.kind == "boost" else (COL_TURQ if p.kind == "shield" else COL_RED)
            pygame.draw.rect(self.canvas, col, (sx - 6, sy - 6, 12, 12), border_radius=2)

    def _draw_missiles(self) -> None:
        for m in self.missiles:
            sx = m.x - self._cam_x
            sy = m.y - self._cam_y + HUD_H
            pygame.draw.circle(self.canvas, COL_RED, (int(sx), int(sy)), 5)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.canvas, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        p = self.karts[0]
        display_lap = min(p.lap + 1, TOTAL_LAPS) if not p.finished else TOTAL_LAPS
        self._pixel_text(f"LAP {display_lap}/{TOTAL_LAPS}", 8, 8, self.font_sm, COL_TURQ)
        self._pixel_text(f"POS {self._player_rank()}/{RACE_KARTS}", 8, 26, self.font_xs, COL_DIM)
        self._pixel_text(f"{self.race_time:.1f}s", WIN_W // 2, 8, self.font_sm, COL_TEXT, center=True)
        best = self.stats.get("best_times", {}).get(self.track_id)
        if best:
            self._pixel_text(f"BEST {best:.1f}s", WIN_W // 2, 26, self.font_xs, COL_DIM, center=True)
        item = (p.held_item or "---").upper()[:7]
        surf = self.font_xs.render(f"ITEM [{item}] SPACE", True, COL_ORANGE)
        self.canvas.blit(surf, (WIN_W - surf.get_width() - 8, 12))

    def draw(self) -> None:
        self.canvas.fill(COL_BG)
        self._buttons.clear()
        if self.screen_id == Screen.TITLE:
            self._draw_title()
        elif self.screen_id == Screen.TRACK_SELECT:
            self._draw_track_select()
        elif self.screen_id == Screen.KART_SELECT:
            self._draw_kart_select()
        elif self.screen_id in (Screen.COUNTDOWN, Screen.RACE, Screen.PAUSED):
            if self.karts:
                self._update_camera()
            self._draw_track()
            for p in self.pickups:
                pass
            self._draw_pickups()
            self._draw_missiles()
            for k in self.karts:
                self._draw_kart(k)
            self._draw_hud()
            if self.screen_id == Screen.COUNTDOWN:
                n = int(self.countdown) + 1
                self._pixel_text(str(n), WIN_W // 2, WIN_H // 2, self.font_lg, COL_TURQ, center=True)
            elif self.screen_id == Screen.PAUSED:
                pygame.draw.rect(self.canvas, (0, 0, 0, 120), (0, HUD_H, WIN_W, WIN_H - HUD_H))
                self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2, self.font_lg, COL_TEXT, center=True)
        elif self.screen_id == Screen.RESULTS:
            self._draw_results()
        self._present()

    def _present(self) -> None:
        self._display.blit(self.canvas, (0, 0))
        pygame.display.flip()

    def _draw_title(self) -> None:
        self._pixel_text("PIXEL KART", WIN_W // 2, 90, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames Premium", WIN_W // 2, 125, self.font_sm, COL_DIM, center=True)
        wins = int(self.stats.get("wins", 0))
        self._pixel_text(f"WINS {wins}  ·  RACES {int(self.stats.get('races', 0))}", WIN_W // 2, 158, self.font_md, COL_GREEN, center=True)
        self._make_btn(220, "RACE", "tracks")
        self._draw_buttons()
        self._pixel_text("ARROWS DRIVE · SPACE USE ITEM", WIN_W // 2, 300, self.font_xs, COL_DIM, center=True)
        self._pixel_text("4 TRACKS · 3 KARTS · 3 LAP RACES", WIN_W // 2, 316, self.font_xs, COL_DIM, center=True)

    def _draw_track_select(self) -> None:
        self._pixel_text("SELECT TRACK", WIN_W // 2, 40, self.font_lg, COL_TURQ, center=True)
        y = 88
        for tid in TRACKS:
            t = TRACKS[tid]
            best = self.stats.get("best_times", {}).get(tid)
            extra = f"  best {best:.1f}s" if best else ""
            self._make_btn(y, f"{t['name']} — {t['desc']}{extra}", f"track:{tid}", 400)
            y += 44
        self._make_btn(y + 8, "BACK", "title", 160)

    def _draw_kart_select(self) -> None:
        self._pixel_text("SELECT KART", WIN_W // 2, 40, self.font_lg, COL_TURQ, center=True)
        y = 100
        for kid in KART_TYPES:
            spec = KART_TYPES[kid]
            self._make_btn(y, f"{spec['name']}  SPD {spec['max_speed']}", f"kart:{kid}", 320)
            y += 48
        self._make_btn(y + 10, "START RACE", "start", 220)
        self._make_btn(y + 56, "BACK", "tracks", 160)

    def _draw_results(self) -> None:
        place = self._result_place
        labels = ["1ST", "2ND", "3RD", "4TH"]
        col = COL_GREEN if place == 1 else COL_TEXT
        self._pixel_text(labels[place - 1], WIN_W // 2, 120, self.font_lg, col, center=True)
        self._pixel_text(f"TIME {self.karts[0].finish_time:.2f}s", WIN_W // 2, 165, self.font_md, COL_TURQ, center=True)
        if place == 1:
            self._pixel_text("NEW RECORD!" if self.stats.get("best_times", {}).get(self.track_id) == round(self.karts[0].finish_time, 2) else "YOU WIN!", WIN_W // 2, 200, self.font_sm, COL_GREEN, center=True)
        self._make_btn(280, "RACE AGAIN", "retry", 220)
        self._make_btn(330, "TRACK SELECT", "tracks", 220)
        self._make_btn(380, "MAIN MENU", "title", 160)

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "tracks":
            self.screen_id = Screen.TRACK_SELECT
        elif action == "title":
            self.screen_id = Screen.TITLE
        elif action.startswith("track:"):
            self.track_id = action.split(":", 1)[1]
            self.screen_id = Screen.KART_SELECT
        elif action.startswith("kart:"):
            self.kart_kind = action.split(":", 1)[1]
        elif action == "start":
            self._start_race()
        elif action == "retry":
            self._start_race()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            act = self._hit_btn(event.pos)
            if act:
                self._do_action(act)
                return
            if self.screen_id == Screen.TITLE:
                self.screen_id = Screen.TRACK_SELECT
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.RACE:
                self.screen_id = Screen.PAUSED
            elif self.screen_id == Screen.PAUSED:
                self.screen_id = Screen.RACE
            elif self.screen_id in (Screen.TRACK_SELECT, Screen.KART_SELECT, Screen.RESULTS):
                self.screen_id = Screen.TITLE
            else:
                self.screen_id = Screen.TITLE
        elif self.screen_id == Screen.RACE and event.key == pygame.K_SPACE:
            self._use_item(self.karts[0])

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(FPS_CAP) / 1000.0, 0.05)
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
    PixelKartGame().run()


if __name__ == "__main__":
    main()
