#!/usr/bin/env python3
"""UsbGames Pixel Chomp — retro maze chase arcade."""

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

GAME_ID = "PixelChomp"

WIN_W, WIN_H = 480, 640
FPS_CAP = 60
HUD_H = 44
TILE = 20

COL_BG = (10, 14, 22)
COL_WALL = (32, 48, 88)
COL_WALL_EDGE = (64, 224, 208)
COL_DOT = (200, 200, 210)
COL_PELLET = (255, 230, 120)
COL_TURQ = (64, 224, 208)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)

SAMPLE_RATE = 22050

# 19 x 15 maze (# wall, . dot, o power pellet)
MAZE_LAYOUT = [
    "###################",
    "#........#........#",
    "#.###.###.#.###.###",
    "#o...............o#",
    "#.###.#.#####.#.###",
    "#.....#..###..#...#",
    "#.###.#.##.##.#.###",
    "#...#.........#...#",
    "#.#.#.#####.#.#.#.#",
    "#.#.#.........#.#.#",
    "#.#.#.#####.#.#.#.#",
    "#.....#..###..#...#",
    "#.###.#.#####.#.###",
    "#o...............o#",
    "#.###.###.#.###.###",
    "#........#........#",
    "###################",
]

PLAYER_START_TILE = (9, 13)
GHOST_START_TILES = [(7, 7), (9, 7), (11, 7), (8, 7)]

GHOST_COLORS = [
    ((255, 90, 90), "blinky"),
    ((255, 180, 200), "pinky"),
    ((64, 224, 208), "inky"),
    ((255, 160, 60), "clyde"),
]

SCATTER_CORNERS = [(1, 1), (17, 1), (1, 15), (17, 15)]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("pixelchomp", "pixel-chomp", "pixel chomp"):
        parent = os.path.dirname(d)
        if os.path.basename(parent).lower() == "portablegames":
            return os.path.dirname(parent)
    return None


HIGHSCORE_LOCAL = os.path.join(app_dir(), "highscore.json")
SETTINGS_PATH = os.path.join(app_dir(), "settings.json")



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


def _present_display(_display: pygame.Surface, _canvas: pygame.Surface) -> None:
    sw, sh = _display.get_size()
    cw, ch = _canvas.get_size()
    if sw == cw and sh == ch:
        _display.blit(_canvas, (0, 0))
    else:
        _display.blit(pygame.transform.smoothscale(_canvas, (sw, sh)), (0, 0))
    pygame.display.flip()


def _map_mouse(_display: pygame.Surface, pos: Tuple[int, int], lw: int, lh: int) -> Tuple[int, int]:
    sw, sh = _display.get_size()
    if sw <= 0 or sh <= 0:
        return pos
    return int(pos[0] * lw / sw), int(pos[1] * lh / sh)


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
            self.chomp = _tone(180, 30, 0.15)
            self.power = _tone(440, 80, 0.25)
            self.eat_ghost = _tone(660, 90, 0.28)
            self.death = _tone(120, 200, 0.3)
            self.ui = _tone(520, 40, 0.2)
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
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _empty_mode_scores() -> dict:
    return {"highscore": 0, "scores": []}


def load_scores() -> dict:
    default = {"classic": _empty_mode_scores(), "speed": _empty_mode_scores()}
    data = load_json(HIGHSCORE_LOCAL, default)
    for mode in ("classic", "speed"):
        if mode not in data or not isinstance(data[mode], dict):
            data[mode] = _empty_mode_scores()
        data[mode]["highscore"] = int(data[mode].get("highscore", 0))
        data[mode]["scores"] = list(data[mode].get("scores", []))[:10]
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            for mode in ("classic", "speed"):
                pm = g.get(mode, {})
                if isinstance(pm, dict):
                    data[mode]["highscore"] = max(
                        data[mode]["highscore"], int(pm.get("highscore", 0))
                    )
                    prof_scores = pm.get("scores", [])
                    if isinstance(prof_scores, list):
                        merged = sorted(
                            set(data[mode]["scores"] + [int(x) for x in prof_scores]),
                            reverse=True,
                        )[:10]
                        data[mode]["scores"] = merged
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


def save_scores(data: dict) -> None:
    save_json(HIGHSCORE_LOCAL, data)
    prof = profile_path()
    if not prof:
        return
    root = load_json(prof, {"profile": "default", "games": {}})
    if "games" not in root or not isinstance(root["games"], dict):
        root["games"] = {}
    root["games"][GAME_ID] = data
    save_json(prof, root)


class Screen(Enum):
    TITLE = auto()
    MODE_SELECT = auto()
    PLAYING = auto()
    PAUSED = auto()
    DYING = auto()
    LEVEL_CLEAR = auto()
    HIGHSCORES = auto()
    SETTINGS = auto()
    GAME_OVER = auto()


class GhostMode(Enum):
    SCATTER = auto()
    CHASE = auto()
    FRIGHTENED = auto()
    EATEN = auto()


@dataclass
class Ghost:
    x: float
    y: float
    dir_x: int
    dir_y: int
    color: Tuple[int, int, int]
    name: str
    mode: GhostMode = GhostMode.SCATTER
    scatter_idx: int = 0


class PixelChompGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Pixel Chomp — UsbGames")
        self._display = pygame.display.set_mode((WIN_W, WIN_H))
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 32, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True})
        self.audio.sfx_on = self.settings.get("sfx", True)
        self.all_scores = load_scores()

        self.rows = len(MAZE_LAYOUT)
        self.cols = len(MAZE_LAYOUT[0])
        self.offset_x = (WIN_W - self.cols * TILE) // 2
        self.offset_y = HUD_H + 36

        self.screen_id = Screen.TITLE
        self.play_mode = "classic"
        self.walls: Set[Tuple[int, int]] = set()
        self.dots: Set[Tuple[int, int]] = set()
        self.pellets: Set[Tuple[int, int]] = set()
        self.score = 0
        self.lives = 3
        self.level = 1
        self.dots_left = 0
        self.player_x = 0.0
        self.player_y = 0.0
        self.player_dir = (0, 0)
        self.want_dir = (0, 0)
        self.mouth = 0.0
        self.ghosts: List[Ghost] = []
        self.mode_timer = 0.0
        self.scatter_phase = True
        self.frightened_timer = 0.0
        self.death_timer = 0.0
        self.level_clear_timer = 0.0
        self.chomp_cooldown = 0.0
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None

    def _pixel_text(
        self, text: str, x: int, y: int, font: pygame.font.Font,
        color: Tuple[int, int, int], center: bool = False,
    ) -> None:
        surf = font.render(text, True, color)
        big = pygame.transform.scale(surf, (surf.get_width() * 2, surf.get_height() * 2))
        pix = pygame.transform.scale(big, (surf.get_width(), surf.get_height()))
        rx = x - pix.get_width() // 2 if center else x
        self.screen.blit(pix, (rx, y))

    def _mode_high(self, mode: str) -> int:
        return int(self.all_scores.get(mode, _empty_mode_scores()).get("highscore", 0))

    def _tile_center(self, gx: int, gy: int) -> Tuple[float, float]:
        return (
            self.offset_x + gx * TILE + TILE / 2,
            self.offset_y + gy * TILE + TILE / 2,
        )

    def _pos_to_tile(self, px: float, py: float) -> Tuple[int, int]:
        gx = int((px - self.offset_x) // TILE)
        gy = int((py - self.offset_y) // TILE)
        return gx, gy

    def _is_wall(self, gx: int, gy: int) -> bool:
        if gx < 0 or gy < 0 or gx >= self.cols or gy >= self.rows:
            return True
        return (gx, gy) in self.walls

    def _can_walk(self, gx: int, gy: int) -> bool:
        if gx < 0 or gy < 0 or gx >= self.cols or gy >= self.rows:
            return False
        return (gx, gy) not in self.walls

    def _parse_maze(self) -> None:
        self.walls.clear()
        self.dots.clear()
        self.pellets.clear()
        for gy, row in enumerate(MAZE_LAYOUT):
            for gx, ch in enumerate(row):
                if ch == "#":
                    self.walls.add((gx, gy))
                elif ch == ".":
                    self.dots.add((gx, gy))
                elif ch == "o":
                    self.pellets.add((gx, gy))
                    self.dots.add((gx, gy))
        self.dots_left = len(self.dots)

    def _player_start(self) -> Tuple[float, float]:
        gx, gy = PLAYER_START_TILE
        if self._can_walk(gx, gy):
            return self._tile_center(gx, gy)
        for gy in range(self.rows - 2, 0, -1):
            for gx in range(self.cols):
                if self._can_walk(gx, gy):
                    return self._tile_center(gx, gy)
        return self._tile_center(self.cols // 2, self.rows - 2)

    def _ghost_starts(self) -> List[Tuple[float, float]]:
        starts: List[Tuple[float, float]] = []
        for gx, gy in GHOST_START_TILES:
            if self._can_walk(gx, gy):
                starts.append(self._tile_center(gx, gy))
        if len(starts) >= 4:
            return starts
        cx, cy = self.cols // 2, self.rows // 2
        return [
            self._tile_center(cx - 1, cy),
            self._tile_center(cx + 1, cy),
            self._tile_center(cx, cy - 1),
            self._tile_center(cx + 1, cy + 1),
        ]

    def _speed_mult(self) -> float:
        base = 1.0 if self.play_mode == "classic" else 1.35
        return base + (self.level - 1) * 0.08

    def _reset_level(self, keep_lives: bool = True) -> None:
        self._parse_maze()
        px, py = self._player_start()
        self.player_x, self.player_y = px, py
        self.player_dir = (0, 0)
        self.want_dir = (0, 0)
        self.ghosts.clear()
        for i, (col, name) in enumerate(GHOST_COLORS):
            sx, sy = self._ghost_starts()[i]
            self.ghosts.append(
                Ghost(sx, sy, -1, 0, col, name, GhostMode.SCATTER, i)
            )
        self.mode_timer = 5.0
        self.scatter_phase = True
        self.frightened_timer = 0.0
        if not keep_lives:
            self.lives = 3
            self.score = 0
            self.level = 1

    def start_game(self, mode: str) -> None:
        self.play_mode = mode
        self._reset_level(keep_lives=False)
        self.screen_id = Screen.PLAYING

    def _activate_power(self) -> None:
        self.frightened_timer = 8.0
        for g in self.ghosts:
            if g.mode != GhostMode.EATEN:
                g.mode = GhostMode.FRIGHTENED
        self.audio.play(self.audio.power)

    def _eat_at(self, gx: int, gy: int) -> None:
        if (gx, gy) in self.pellets:
            self.pellets.discard((gx, gy))
            self.dots.discard((gx, gy))
            self.dots_left -= 1
            self.score += 50
            self._activate_power()
            self.audio.play(self.audio.chomp)
        elif (gx, gy) in self.dots:
            self.dots.discard((gx, gy))
            self.dots_left -= 1
            self.score += 10
            if self.chomp_cooldown <= 0:
                self.audio.play(self.audio.chomp)
                self.chomp_cooldown = 0.08

    def _try_player_dir(self, dx: int, dy: int) -> bool:
        speed = 90.0 * self._speed_mult()
        nx = self.player_x + dx * speed * (1 / FPS_CAP)
        ny = self.player_y + dy * speed * (1 / FPS_CAP)
        margin = 6
        corners = [
            (nx - margin, ny - margin),
            (nx + margin, ny - margin),
            (nx - margin, ny + margin),
            (nx + margin, ny + margin),
        ]
        for cx, cy in corners:
            gx, gy = self._pos_to_tile(cx, cy)
            if self._is_wall(gx, gy):
                return False
        self.player_x, self.player_y = nx, ny
        self.player_dir = (dx, dy)
        return True

    def _pick_ghost_dir(self, g: Ghost) -> Tuple[int, int]:
        options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(options)
        gx, gy = self._pos_to_tile(g.x, g.y)
        target = (gx, gy)
        if g.mode == GhostMode.FRIGHTENED:
            target = (random.randint(0, self.cols - 1), random.randint(0, self.rows - 1))
        elif g.mode == GhostMode.SCATTER:
            target = SCATTER_CORNERS[g.scatter_idx]
        elif g.mode == GhostMode.CHASE:
            target = self._pos_to_tile(self.player_x, self.player_y)
        elif g.mode == GhostMode.EATEN:
            target = (self.cols // 2, self.rows // 2)

        best = None
        best_dist = 1e9
        for dx, dy in options:
            if (dx, dy) == (-g.dir_x, -g.dir_y) and len(options) > 1:
                continue
            ngx, ngy = gx + dx, gy + dy
            if not self._can_walk(ngx, ngy):
                continue
            dist = (ngx - target[0]) ** 2 + (ngy - target[1]) ** 2
            if g.mode == GhostMode.FRIGHTENED:
                dist = random.random()
            if dist < best_dist:
                best_dist = dist
                best = (dx, dy)
        if best:
            return best
        return (-g.dir_x, -g.dir_y) if (g.dir_x, g.dir_y) != (0, 0) else (1, 0)

    def _move_ghost(self, g: Ghost, dt: float) -> None:
        speed = (70.0 if g.mode == GhostMode.FRIGHTENED else 85.0) * self._speed_mult()
        if g.mode == GhostMode.EATEN:
            speed = 110.0 * self._speed_mult()
        gx, gy = self._pos_to_tile(g.x, g.y)
        tcx, tcy = self._tile_center(gx, gy)
        if abs(g.x - tcx) < 3 and abs(g.y - tcy) < 3:
            g.dir_x, g.dir_y = self._pick_ghost_dir(g)
        g.x += g.dir_x * speed * dt
        g.y += g.dir_y * speed * dt

    def _ghost_hit_player(self, g: Ghost) -> None:
        if g.mode == GhostMode.EATEN:
            return
        dist = math.hypot(g.x - self.player_x, g.y - self.player_y)
        if dist > TILE * 0.55:
            return
        if g.mode == GhostMode.FRIGHTENED:
            g.mode = GhostMode.EATEN
            self.score += 200 * self.level
            self.audio.play(self.audio.eat_ghost)
            return
        self._player_die()

    def _player_die(self) -> None:
        self.lives -= 1
        self.audio.play(self.audio.death)
        self.death_timer = 2.0
        self.screen_id = Screen.DYING

    def _after_death(self) -> None:
        if self.lives <= 0:
            self._game_over()
            return
        px, py = self._player_start()
        self.player_x, self.player_y = px, py
        self.player_dir = (0, 0)
        self.want_dir = (0, 0)
        for i, g in enumerate(self.ghosts):
            sx, sy = self._ghost_starts()[i]
            g.x, g.y = sx, sy
            g.mode = GhostMode.SCATTER
            g.dir_x, g.dir_y = -1, 0
        self.frightened_timer = 0.0
        self.screen_id = Screen.PLAYING

    def _game_over(self) -> None:
        mode = self.all_scores.setdefault(self.play_mode, _empty_mode_scores())
        if self.score > int(mode.get("highscore", 0)):
            mode["highscore"] = self.score
        scores = list(mode.get("scores", []))
        scores.insert(0, self.score)
        mode["scores"] = sorted(set(scores), reverse=True)[:10]
        save_scores(self.all_scores)
        self.screen_id = Screen.GAME_OVER

    def update(self, dt: float) -> None:
        if self.screen_id == Screen.DYING:
            self.death_timer -= dt
            if self.death_timer <= 0:
                self._after_death()
            return

        if self.screen_id == Screen.LEVEL_CLEAR:
            self.level_clear_timer -= dt
            if self.level_clear_timer <= 0:
                self.level += 1
                self._reset_level(keep_lives=True)
                self.screen_id = Screen.PLAYING
            return

        if self.screen_id != Screen.PLAYING:
            return

        if self.chomp_cooldown > 0:
            self.chomp_cooldown -= dt

        self.mouth += dt * 8

        if self.frightened_timer > 0:
            self.frightened_timer -= dt
            if self.frightened_timer <= 0:
                for g in self.ghosts:
                    if g.mode == GhostMode.FRIGHTENED:
                        g.mode = GhostMode.CHASE

        self.mode_timer -= dt
        if self.mode_timer <= 0:
            self.scatter_phase = not self.scatter_phase
            self.mode_timer = 6.0 if self.scatter_phase else 10.0
            for g in self.ghosts:
                if g.mode in (GhostMode.CHASE, GhostMode.SCATTER):
                    g.mode = GhostMode.SCATTER if self.scatter_phase else GhostMode.CHASE

        wx, wy = self.want_dir
        if wx != 0 or wy != 0:
            self._try_player_dir(wx, wy)
        elif self.player_dir != (0, 0):
            self._try_player_dir(self.player_dir[0], self.player_dir[1])

        gx, gy = self._pos_to_tile(self.player_x, self.player_y)
        self._eat_at(gx, gy)
        for ox, oy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            self._eat_at(gx + ox, gy + oy)

        if self.dots_left <= 0:
            self.level_clear_timer = 2.0
            self.screen_id = Screen.LEVEL_CLEAR
            return

        for g in self.ghosts:
            self._move_ghost(g, dt)
            self._ghost_hit_player(g)

    def _draw_maze(self) -> None:
        for gy in range(self.rows):
            for gx in range(self.cols):
                x = self.offset_x + gx * TILE
                y = self.offset_y + gy * TILE
                if (gx, gy) in self.walls:
                    pygame.draw.rect(self.screen, COL_WALL, (x, y, TILE, TILE))
                    pygame.draw.rect(self.screen, COL_WALL_EDGE, (x, y, TILE, TILE), 1)
                elif (gx, gy) in self.dots:
                    pygame.draw.circle(
                        self.screen, COL_DOT,
                        (x + TILE // 2, y + TILE // 2), 2,
                    )
                if (gx, gy) in self.pellets:
                    pygame.draw.circle(
                        self.screen, COL_PELLET,
                        (x + TILE // 2, y + TILE // 2), 5,
                    )

    def _draw_player(self) -> None:
        mouth_open = (math.sin(self.mouth) + 1) * 0.35 + 0.1
        angle = 0.0
        if self.player_dir == (1, 0):
            angle = 0
        elif self.player_dir == (-1, 0):
            angle = math.pi
        elif self.player_dir == (0, -1):
            angle = -math.pi / 2
        elif self.player_dir == (0, 1):
            angle = math.pi / 2
        r = TILE // 2 - 2
        start = angle + mouth_open * math.pi
        end = angle - mouth_open * math.pi
        rect = pygame.Rect(0, 0, r * 2, r * 2)
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 230, 80), (r, r), r)
        pygame.draw.polygon(
            surf, COL_BG,
            [(r, r),
             (r + r * math.cos(start), r + r * math.sin(start)),
             (r + r * math.cos(end), r + r * math.sin(end))],
        )
        self.screen.blit(surf, (int(self.player_x - r), int(self.player_y - r)))

    def _draw_ghost(self, g: Ghost) -> None:
        if g.mode == GhostMode.EATEN:
            col = (80, 80, 100)
        elif g.mode == GhostMode.FRIGHTENED:
            col = (60, 80, 255) if int(self.frightened_timer * 4) % 2 == 0 else (200, 200, 255)
        else:
            col = g.color
        r = TILE // 2 - 2
        pygame.draw.circle(self.screen, col, (int(g.x), int(g.y - 2)), r)
        pygame.draw.rect(
            self.screen, col,
            (int(g.x - r), int(g.y), r * 2, r // 2 + 2),
        )
        eye = COL_BG if g.mode != GhostMode.FRIGHTENED else COL_TEXT
        pygame.draw.circle(self.screen, eye, (int(g.x - 4), int(g.y - 4)), 2)
        pygame.draw.circle(self.screen, eye, (int(g.x + 4), int(g.y - 4)), 2)

    def _make_btn(self, y: int, label: str, action: str, w: int = 220) -> None:
        self._buttons.append((pygame.Rect(WIN_W // 2 - w // 2, y, w, 38), label, action))

    def _draw_buttons(self) -> None:
        for rect, label, action in self._buttons:
            hover = self._hover == action
            pygame.draw.rect(self.screen, COL_BTN_HOVER if hover else COL_BTN, rect)
            pygame.draw.rect(self.screen, COL_TURQ if hover else COL_DIM, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 8, self.font_md, COL_TEXT, center=True)

    def draw(self) -> None:
        self.screen.fill(COL_BG)
        self._buttons.clear()

        if self.screen_id == Screen.TITLE:
            self._pixel_text("PIXEL CHOMP", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
            self._pixel_text("UsbGames", WIN_W // 2, 150, self.font_sm, COL_DIM, center=True)
            self._draw_title_demo()
            best = max(self._mode_high("classic"), self._mode_high("speed"))
            self._pixel_text(f"BEST {best}", WIN_W // 2, 220, self.font_md, COL_GREEN, center=True)
            self._make_btn(280, "PLAY", "modes")
            self._make_btn(335, "HIGHSCORES", "highscores")
            self._make_btn(390, "SETTINGS", "settings")
            self._draw_buttons()
            self._pixel_text("ARROWS — MOVE", WIN_W // 2, WIN_H - 60, self.font_xs, COL_DIM, center=True)
        elif self.screen_id == Screen.MODE_SELECT:
            self._pixel_text("SELECT MODE", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
            self._make_btn(280, "CLASSIC", "classic")
            self._make_btn(335, "SPEED RUN", "speed")
            self._make_btn(400, "BACK", "title")
            self._draw_buttons()
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED, Screen.DYING, Screen.LEVEL_CLEAR):
            pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
            self._pixel_text(
                f"SCORE {self.score}", 10, 8, self.font_sm, COL_TEXT,
            )
            self._pixel_text(
                f"LV {self.level}", WIN_W // 2, 8, self.font_sm, COL_TURQ, center=True,
            )
            hearts = "♥" * self.lives + "♡" * max(0, 3 - self.lives)
            self._pixel_text(hearts, WIN_W - 60, 8, self.font_sm, (255, 90, 90))
            self._draw_maze()
            for g in self.ghosts:
                self._draw_ghost(g)
            if self.screen_id != Screen.DYING:
                self._draw_player()
            if self.screen_id == Screen.PAUSED:
                ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 160))
                self.screen.blit(ov, (0, 0))
                self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2, self.font_lg, COL_TURQ, center=True)
            elif self.screen_id == Screen.LEVEL_CLEAR:
                self._pixel_text("LEVEL CLEAR!", WIN_W // 2, WIN_H // 2, self.font_lg, COL_GREEN, center=True)
        elif self.screen_id == Screen.HIGHSCORES:
            self._draw_highscores()
        elif self.screen_id == Screen.SETTINGS:
            self._draw_settings()
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_maze()
            ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 175))
            self.screen.blit(ov, (0, 0))
            self._pixel_text("GAME OVER", WIN_W // 2, 150, self.font_lg, COL_TURQ, center=True)
            self._pixel_text(f"SCORE {self.score}", WIN_W // 2, 210, self.font_md, COL_TEXT, center=True)
            self._make_btn(360, "RETRY", f"retry_{self.play_mode}")
            self._make_btn(415, "MENU", "title")
            self._draw_buttons()

        _present_display(self._display, self.screen)

    def _draw_title_demo(self) -> None:
        colors = [(255, 230, 80)] + [c[0] for c in GHOST_COLORS]
        for i, col in enumerate(colors):
            pygame.draw.circle(self.screen, col, (160 + i * 40, 270), 12)

    def _draw_highscores(self) -> None:
        self._pixel_text("HIGHSCORES", WIN_W // 2, 56, self.font_lg, COL_TURQ, center=True)
        y = 110
        for mode, label in (("classic", "CLASSIC"), ("speed", "SPEED")):
            self._pixel_text(label, 48, y, self.font_md, COL_GREEN)
            data = self.all_scores.get(mode, _empty_mode_scores())
            self._pixel_text(f"Best: {data.get('highscore', 0)}", 48, y + 28, self.font_sm, COL_TEXT)
            for i, sc in enumerate(list(data.get("scores", []))[:5]):
                self._pixel_text(f"{i + 1}. {sc}", 64, y + 52 + i * 22, self.font_xs, COL_DIM)
            y += 200
        self._make_btn(560, "BACK", "title")
        self._draw_buttons()

    def _draw_settings(self) -> None:
        sfx = "ON" if self.settings.get("sfx", True) else "OFF"
        self._pixel_text("SETTINGS", WIN_W // 2, 56, self.font_lg, COL_TURQ, center=True)
        self._pixel_text(f"SFX: {sfx}", WIN_W // 2, 140, self.font_md, COL_TEXT, center=True)
        self._make_btn(300, "TOGGLE SFX", "toggle_sfx")
        self._make_btn(360, "BACK", "title")
        self._draw_buttons()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "modes":
            self.screen_id = Screen.MODE_SELECT
        elif action in ("classic", "speed"):
            self.start_game(action)
        elif action.startswith("retry_"):
            self.start_game(action.split("_", 1)[1])
        elif action == "highscores":
            self.all_scores = load_scores()
            self.screen_id = Screen.HIGHSCORES
        elif action == "settings":
            self.screen_id = Screen.SETTINGS
        elif action == "toggle_sfx":
            self.settings["sfx"] = not self.settings.get("sfx", True)
            save_json(SETTINGS_PATH, self.settings)
            self.audio.sfx_on = self.settings["sfx"]
        elif action == "title":
            self.screen_id = Screen.TITLE

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            act = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
            if act:
                self._do_action(act)
                return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.PAUSED
            elif self.screen_id == Screen.PAUSED:
                self.screen_id = Screen.PLAYING
            elif self.screen_id in (Screen.MODE_SELECT, Screen.HIGHSCORES, Screen.SETTINGS):
                self.screen_id = Screen.TITLE
            elif self.screen_id == Screen.GAME_OVER:
                self.screen_id = Screen.TITLE
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.screen_id == Screen.TITLE:
                self.screen_id = Screen.MODE_SELECT
            elif self.screen_id == Screen.MODE_SELECT:
                self.start_game("classic")
            return
        if self.screen_id == Screen.PLAYING:
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self.want_dir = (1, 0)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.want_dir = (-1, 0)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.want_dir = (0, 1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.want_dir = (0, -1)

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
    PixelChompGame().run()


if __name__ == "__main__":
    main()
