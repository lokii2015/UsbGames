#!/usr/bin/env python3
"""UsbGames BlockStack DX — retro falling-block puzzle."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame

GAME_ID = "BlockStackDX"

WIN_W, WIN_H = 480, 640
FPS_CAP = 60
HUD_H = 44

COLS, ROWS = 10, 20
CELL = 22
BOARD_W = COLS * CELL
BOARD_X = 28
BOARD_Y = HUD_H + 52
SIDE_X = BOARD_X + BOARD_W + 14

COL_BG = (10, 14, 22)
COL_BG2 = (14, 20, 32)
COL_GRID = (22, 30, 44)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 140, 128)
COL_GREEN = (57, 255, 120)
COL_PURPLE = (180, 120, 255)
COL_PURPLE_DIM = (90, 60, 120)

SAMPLE_RATE = 22050

PIECES = ("I", "O", "T", "S", "Z", "J", "L")

SHAPES: Dict[str, List[List[int]]] = {
    "I": [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ],
    "O": [
        [1, 1],
        [1, 1],
    ],
    "T": [
        [0, 1, 0],
        [1, 1, 1],
        [0, 0, 0],
    ],
    "S": [
        [0, 1, 1],
        [1, 1, 0],
        [0, 0, 0],
    ],
    "Z": [
        [1, 1, 0],
        [0, 1, 1],
        [0, 0, 0],
    ],
    "J": [
        [1, 0, 0],
        [1, 1, 1],
        [0, 0, 0],
    ],
    "L": [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0],
    ],
}

THEMES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "neon": {
        "I": COL_TURQ,
        "O": (255, 230, 120),
        "T": COL_PURPLE,
        "S": COL_GREEN,
        "Z": (255, 90, 90),
        "J": (64, 160, 255),
        "L": (255, 160, 60),
        "ghost": (40, 70, 68),
        "grid": COL_GRID,
        "accent": COL_TURQ,
    },
    "matrix": {
        "I": (80, 255, 140),
        "O": (120, 255, 100),
        "T": (60, 220, 120),
        "S": (40, 200, 100),
        "Z": (100, 255, 160),
        "J": (30, 180, 90),
        "L": (160, 255, 120),
        "ghost": (20, 60, 35),
        "grid": (16, 40, 28),
        "accent": COL_GREEN,
    },
    "violet": {
        "I": (200, 140, 255),
        "O": (255, 120, 220),
        "T": (160, 100, 255),
        "S": (220, 80, 255),
        "Z": (140, 90, 220),
        "J": (255, 160, 240),
        "L": (180, 120, 255),
        "ghost": (50, 35, 70),
        "grid": (32, 24, 48),
        "accent": COL_PURPLE,
    },
}

THEME_NAMES = list(THEMES.keys())


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("blockstackdx", "block-stack-dx", "block stack dx"):
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
            self.move = _tone(320, 25, 0.12)
            self.rotate = _tone(480, 35, 0.18)
            self.drop = _tone(180, 40, 0.2)
            self.lock = _tone(220, 50, 0.22)
            self.line1 = _tone(520, 60, 0.25)
            self.line2 = _tone(620, 70, 0.28)
            self.line3 = _tone(720, 80, 0.3)
            self.line4 = _tone(880, 100, 0.35)
            self.gameover = _tone(140, 140, 0.3)
            self.ui = _tone(440, 40, 0.2)
        except pygame.error:
            self.enabled = False

    def play(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and self.sfx_on and snd:
            snd.play()

    def line_clear(self, lines: int) -> None:
        snd = {1: self.line1, 2: self.line2, 3: self.line3, 4: self.line4}.get(lines, self.line4)
        self.play(snd)


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


def rotate_cw(matrix: List[List[int]]) -> List[List[int]]:
    h, w = len(matrix), len(matrix[0])
    return [[matrix[h - 1 - r][c] for r in range(h)] for c in range(w)]


def piece_cells(kind: str, rot: int) -> List[Tuple[int, int]]:
    m = [row[:] for row in SHAPES[kind]]
    for _ in range(rot % 4):
        m = rotate_cw(m)
    cells: List[Tuple[int, int]] = []
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                cells.append((x, y))
    return cells


class Screen(Enum):
    TITLE = auto()
    MODE_SELECT = auto()
    PLAYING = auto()
    PAUSED = auto()
    HIGHSCORES = auto()
    SETTINGS = auto()
    GAME_OVER = auto()


class BlockStackDXGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("BlockStack DX — UsbGames")
        self._display = pygame.display.set_mode((WIN_W, WIN_H))
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 32, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True, "theme": "neon"})
        if self.settings.get("theme") not in THEMES:
            self.settings["theme"] = "neon"
        self.audio.sfx_on = self.settings.get("sfx", True)

        self.all_scores = load_scores()
        self.screen_id = Screen.TITLE
        self.play_mode = "classic"
        self.grid: List[List[Optional[str]]] = []
        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo_chain = 0
        self.combo_display = 0.0
        self.piece_kind = "T"
        self.piece_rot = 0
        self.piece_x = 0
        self.piece_y = 0
        self.next_kind = "I"
        self.bag: List[str] = []
        self.drop_timer = 0.0
        self.lock_timer = 0.0
        self.lock_moves = 0
        self.soft_drop = False
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._das_timer = 0.0
        self._das_dir = 0
        self._keys_held = {
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_DOWN: False,
            pygame.K_a: False,
            pygame.K_d: False,
            pygame.K_s: False,
        }

    def _theme(self) -> dict:
        return THEMES[self.settings.get("theme", "neon")]

    def _pixel_text(
        self,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        center: bool = False,
    ) -> None:
        surf = font.render(text, True, color)
        big = pygame.transform.scale(surf, (surf.get_width() * 2, surf.get_height() * 2))
        pix = pygame.transform.scale(big, (surf.get_width(), surf.get_height()))
        rx = x - pix.get_width() // 2 if center else x
        self.screen.blit(pix, (rx, y))

    def _mode_high(self, mode: str) -> int:
        return int(self.all_scores.get(mode, _empty_mode_scores()).get("highscore", 0))

    def _refill_bag(self) -> None:
        self.bag = list(PIECES)
        random.shuffle(self.bag)

    def _next_from_bag(self) -> str:
        if not self.bag:
            self._refill_bag()
        return self.bag.pop()

    def _drop_interval(self) -> float:
        base = 0.85 if self.play_mode == "classic" else 0.45
        speed = max(0.08, base - (self.level - 1) * 0.06)
        if self.soft_drop:
            return 0.04
        return speed

    def _new_grid(self) -> List[List[Optional[str]]]:
        return [[None for _ in range(COLS)] for _ in range(ROWS)]

    def _spawn_piece(self) -> bool:
        self.piece_kind = self.next_kind
        self.next_kind = self._next_from_bag()
        self.piece_rot = 0
        cells = piece_cells(self.piece_kind, self.piece_rot)
        min_x = min(c[0] for c in cells)
        max_x = max(c[0] for c in cells)
        self.piece_x = (COLS - (max_x - min_x + 1)) // 2 - min_x
        self.piece_y = -min(c[1] for c in cells)
        self.lock_timer = 0.0
        self.lock_moves = 0
        if self._collides(self.piece_x, self.piece_y, self.piece_kind, self.piece_rot):
            return False
        return True

    def _collides(self, px: int, py: int, kind: str, rot: int) -> bool:
        for cx, cy in piece_cells(kind, rot):
            x, y = px + cx, py + cy
            if x < 0 or x >= COLS or y >= ROWS:
                return True
            if y >= 0 and self.grid[y][x] is not None:
                return True
        return False

    def _lock_piece(self) -> None:
        for cx, cy in piece_cells(self.piece_kind, self.piece_rot):
            x, y = self.piece_x + cx, self.piece_y + cy
            if 0 <= y < ROWS and 0 <= x < COLS:
                self.grid[y][x] = self.piece_kind
        self.audio.play(self.audio.lock)
        cleared = self._clear_lines()
        if cleared:
            self.combo_chain += 1
            self.combo_display = 1.2
            mult = 1 + (self.combo_chain - 1) * 0.25
            base = {1: 100, 2: 300, 3: 500, 4: 800}.get(cleared, 800)
            self.score += int(base * self.level * mult)
            self.lines += cleared
            self.level = 1 + self.lines // 10
            self.audio.line_clear(cleared)
        else:
            self.combo_chain = 0
        if not self._spawn_piece():
            self._game_over()

    def _clear_lines(self) -> int:
        full = [r for r in range(ROWS) if all(self.grid[r][c] is not None for c in range(COLS))]
        if not full:
            return 0
        for r in full:
            del self.grid[r]
            self.grid.insert(0, [None for _ in range(COLS)])
        return len(full)

    def _try_move(self, dx: int, dy: int) -> bool:
        if not self._collides(self.piece_x + dx, self.piece_y + dy, self.piece_kind, self.piece_rot):
            self.piece_x += dx
            self.piece_y += dy
            if dy == 0:
                self.lock_moves += 1
                self.lock_timer = 0.0
            return True
        return False

    def _try_rotate(self) -> bool:
        new_rot = (self.piece_rot + 1) % 4
        kicks = [(0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0)]
        for kx, ky in kicks:
            if not self._collides(self.piece_x + kx, self.piece_y + ky, self.piece_kind, new_rot):
                self.piece_rot = new_rot
                self.piece_x += kx
                self.piece_y += ky
                self.lock_moves += 1
                self.lock_timer = 0.0
                self.audio.play(self.audio.rotate)
                return True
        return False

    def _hard_drop(self) -> None:
        dist = 0
        while self._try_move(0, 1):
            dist += 1
        self.score += dist * 2
        self.audio.play(self.audio.drop)
        self._lock_piece()

    def start_game(self, mode: str) -> None:
        self.play_mode = mode
        self.grid = self._new_grid()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo_chain = 0
        self.combo_display = 0.0
        self._refill_bag()
        self.next_kind = self._next_from_bag()
        self.drop_timer = 0.0
        self.soft_drop = False
        if not self._spawn_piece():
            self._game_over()
            return
        self.screen_id = Screen.PLAYING

    def _game_over(self) -> None:
        self.audio.play(self.audio.gameover)
        mode = self.all_scores.setdefault(self.play_mode, _empty_mode_scores())
        if self.score > int(mode.get("highscore", 0)):
            mode["highscore"] = self.score
        scores = list(mode.get("scores", []))
        scores.insert(0, self.score)
        mode["scores"] = sorted(set(scores), reverse=True)[:10]
        save_scores(self.all_scores)
        self.screen_id = Screen.GAME_OVER

    def _active_cells(self) -> List[Tuple[int, int, str]]:
        out: List[Tuple[int, int, str]] = []
        for cx, cy in piece_cells(self.piece_kind, self.piece_rot):
            out.append((self.piece_x + cx, self.piece_y + cy, self.piece_kind))
        return out

    def _ghost_y(self) -> int:
        gy = self.piece_y
        while not self._collides(self.piece_x, gy + 1, self.piece_kind, self.piece_rot):
            gy += 1
        return gy

    def update(self, dt: float) -> None:
        if self.screen_id != Screen.PLAYING:
            return

        if self.combo_display > 0:
            self.combo_display -= dt

        move_dir = 0
        if self._keys_held[pygame.K_LEFT] or self._keys_held[pygame.K_a]:
            move_dir = -1
        elif self._keys_held[pygame.K_RIGHT] or self._keys_held[pygame.K_d]:
            move_dir = 1

        if move_dir != 0:
            if move_dir != self._das_dir:
                self._das_dir = move_dir
                self._das_timer = 0.0
                if self._try_move(move_dir, 0):
                    self.audio.play(self.audio.move)
            else:
                self._das_timer += dt
                if self._das_timer >= 0.12:
                    self._das_timer = 0.08
                    if self._try_move(move_dir, 0):
                        self.audio.play(self.audio.move)
        else:
            self._das_dir = 0
            self._das_timer = 0.0

        self.soft_drop = self._keys_held[pygame.K_DOWN] or self._keys_held[pygame.K_s]
        self.drop_timer += dt
        interval = self._drop_interval()
        if self.drop_timer >= interval:
            self.drop_timer = 0.0
            if self._try_move(0, 1):
                self.lock_timer = 0.0
                if self.soft_drop:
                    self.score += 1
            else:
                self.lock_timer += dt
                if self.lock_timer >= 0.5 or self.lock_moves >= 15:
                    self._lock_piece()

    def _cell_rect(self, gx: int, gy: int) -> pygame.Rect:
        return pygame.Rect(BOARD_X + gx * CELL, BOARD_Y + gy * CELL, CELL - 1, CELL - 1)

    def _draw_block(self, rect: pygame.Rect, color: Tuple[int, int, int], ghost: bool = False) -> None:
        if ghost:
            pygame.draw.rect(self.screen, color, rect, 2, border_radius=2)
            return
        pygame.draw.rect(self.screen, color, rect, border_radius=2)
        inner = rect.inflate(-4, -4)
        hi = tuple(min(255, c + 50) for c in color)
        pygame.draw.rect(self.screen, hi, inner, border_radius=2)
        pygame.draw.rect(self.screen, tuple(max(0, c - 40) for c in color), rect, 1, border_radius=2)

    def _draw_board(self) -> None:
        th = self._theme()
        frame = pygame.Rect(BOARD_X - 6, BOARD_Y - 6, BOARD_W + 12, ROWS * CELL + 12)
        pygame.draw.rect(self.screen, COL_BG2, frame, border_radius=4)
        pygame.draw.rect(self.screen, th["accent"], frame, 2, border_radius=4)
        for gy in range(ROWS):
            for gx in range(COLS):
                r = self._cell_rect(gx, gy)
                pygame.draw.rect(self.screen, th["grid"], r)
                kind = self.grid[gy][gx]
                if kind:
                    self._draw_block(r, th[kind])

        ghost_y = self._ghost_y()
        for cx, cy in piece_cells(self.piece_kind, self.piece_rot):
            gx, gy = self.piece_x + cx, ghost_y + cy
            if gy >= 0:
                self._draw_block(self._cell_rect(gx, gy), th["ghost"], ghost=True)

        for gx, gy, kind in self._active_cells():
            if gy >= 0:
                self._draw_block(self._cell_rect(gx, gy), th[kind])

    def _draw_mini_piece(self, kind: str, cx: int, cy: int, size: int = 14) -> None:
        th = self._theme()
        cells = piece_cells(kind, 0)
        min_x = min(c[0] for c in cells)
        min_y = min(c[1] for c in cells)
        for px, py in cells:
            r = pygame.Rect(cx + (px - min_x) * size, cy + (py - min_y) * size, size - 2, size - 2)
            self._draw_block(r, th[kind])

    def _draw_side_panel(self) -> None:
        th = self._theme()
        self._pixel_text("NEXT", SIDE_X, BOARD_Y, self.font_xs, COL_DIM)
        self._draw_mini_piece(self.next_kind, SIDE_X + 8, BOARD_Y + 22)

        self._pixel_text("SCORE", SIDE_X, BOARD_Y + 90, self.font_xs, COL_DIM)
        self._pixel_text(str(self.score), SIDE_X, BOARD_Y + 110, self.font_sm, COL_TEXT)

        self._pixel_text("LINES", SIDE_X, BOARD_Y + 150, self.font_xs, COL_DIM)
        self._pixel_text(str(self.lines), SIDE_X, BOARD_Y + 170, self.font_sm, COL_TEXT)

        self._pixel_text("LEVEL", SIDE_X, BOARD_Y + 210, self.font_xs, COL_DIM)
        self._pixel_text(str(self.level), SIDE_X, BOARD_Y + 230, self.font_sm, th["accent"])

        mode_label = "CLASSIC" if self.play_mode == "classic" else "SPEED"
        self._pixel_text(mode_label, SIDE_X, BOARD_Y + 270, self.font_xs, COL_DIM)

        if self.combo_chain > 1 and self.combo_display > 0:
            self._pixel_text(
                f"COMBO x{self.combo_chain}",
                SIDE_X,
                BOARD_Y + 310,
                self.font_xs,
                COL_GREEN,
            )

    def _draw_bg_stars(self) -> None:
        rng = random.Random(42)
        for _ in range(40):
            x, y = rng.randint(0, WIN_W - 1), rng.randint(HUD_H, WIN_H - 1)
            c = rng.choice([COL_TURQ_DIM, (40, 55, 70), COL_PURPLE_DIM])
            if y < BOARD_Y - 10 or x > BOARD_X + BOARD_W + 20:
                self.screen.set_at((x, y), c)

    def _make_btn(self, y: int, label: str, action: str, w: int = 220) -> None:
        self._buttons.append((pygame.Rect(WIN_W // 2 - w // 2, y, w, 38), label, action))

    def _draw_buttons(self) -> None:
        th = self._theme()
        for rect, label, action in self._buttons:
            hover = self._hover == action
            pygame.draw.rect(self.screen, COL_BTN_HOVER if hover else COL_BTN, rect)
            pygame.draw.rect(self.screen, th["accent"] if hover else COL_DIM, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 8, self.font_md, COL_TEXT, center=True)

    def draw(self) -> None:
        self.screen.fill(COL_BG)
        self._buttons.clear()
        th = self._theme()

        if self.screen_id == Screen.TITLE:
            self._draw_bg_stars()
            pygame.draw.rect(self.screen, th["accent"], (20, 48, WIN_W - 40, 4))
            self._pixel_text("BLOCKSTACK", WIN_W // 2, 88, self.font_lg, th["accent"], center=True)
            self._pixel_text("DX", WIN_W // 2, 128, self.font_lg, COL_GREEN, center=True)
            self._pixel_text("UsbGames", WIN_W // 2, 168, self.font_sm, COL_DIM, center=True)
            self._draw_title_blocks()
            best = max(self._mode_high("classic"), self._mode_high("speed"))
            self._pixel_text(f"BEST {best}", WIN_W // 2, 220, self.font_md, COL_GREEN, center=True)
            self._make_btn(280, "PLAY", "modes")
            self._make_btn(335, "HIGHSCORES", "highscores")
            self._make_btn(390, "SETTINGS", "settings")
            self._draw_buttons()
            self._pixel_text("ARROWS — MOVE / ROTATE", WIN_W // 2, WIN_H - 72, self.font_xs, COL_DIM, center=True)
            self._pixel_text("SPACE — HARD DROP", WIN_W // 2, WIN_H - 52, self.font_xs, COL_DIM, center=True)
        elif self.screen_id == Screen.MODE_SELECT:
            self._draw_bg_stars()
            self._pixel_text("SELECT MODE", WIN_W // 2, 100, self.font_lg, th["accent"], center=True)
            self._pixel_text(
                f"Classic best: {self._mode_high('classic')}",
                WIN_W // 2,
                160,
                self.font_sm,
                COL_DIM,
                center=True,
            )
            self._pixel_text(
                f"Speed best: {self._mode_high('speed')}",
                WIN_W // 2,
                190,
                self.font_sm,
                COL_DIM,
                center=True,
            )
            self._make_btn(280, "CLASSIC MODE", "classic")
            self._make_btn(335, "SPEED MODE", "speed")
            self._make_btn(400, "BACK", "title")
            self._draw_buttons()
        elif self.screen_id == Screen.HIGHSCORES:
            self._draw_highscores()
        elif self.screen_id == Screen.SETTINGS:
            self._draw_settings()
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED):
            self._draw_bg_stars()
            self._draw_board()
            self._draw_side_panel()
            self._draw_play_hud()
            if self.screen_id == Screen.PAUSED:
                self._draw_pause_overlay()
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_bg_stars()
            self._draw_board()
            self._draw_side_panel()
            self._draw_play_hud()
            self._draw_game_over()

        _present_display(self._display, self.screen)

    def _draw_title_blocks(self) -> None:
        th = self._theme()
        preview = [("T", 0), ("I", 1), ("O", 0), ("L", 2)]
        x0 = WIN_W // 2 - len(preview) * 28
        for i, (kind, rot) in enumerate(preview):
            cells = piece_cells(kind, rot)
            min_x = min(c[0] for c in cells)
            min_y = min(c[1] for c in cells)
            for px, py in cells:
                r = pygame.Rect(x0 + i * 56 + (px - min_x) * 12, 250 + (py - min_y) * 12, 11, 11)
                self._draw_block(r, th[kind])

    def _draw_play_hud(self) -> None:
        th = self._theme()
        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        self._pixel_text("BLOCKSTACK DX", 12, 8, self.font_sm, th["accent"])
        surf = self.font_xs.render(f"SCORE {self.score}", True, COL_TEXT)
        self._pixel_text(f"SCORE {self.score}", WIN_W - surf.get_width() - 12, 26, self.font_xs, COL_TEXT)

    def _draw_pause_overlay(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2 - 20, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("ESC — RESUME", WIN_W // 2, WIN_H // 2 + 24, self.font_xs, COL_DIM, center=True)

    def _draw_game_over(self) -> None:
        th = self._theme()
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("GAME OVER", WIN_W // 2, 140, self.font_lg, th["accent"], center=True)
        self._pixel_text(f"SCORE {self.score}", WIN_W // 2, 195, self.font_md, COL_TEXT, center=True)
        self._pixel_text(f"LINES {self.lines}", WIN_W // 2, 230, self.font_sm, COL_DIM, center=True)
        best = self._mode_high(self.play_mode)
        self._pixel_text(f"BEST {best}", WIN_W // 2, 265, self.font_sm, COL_GREEN, center=True)
        if self.score >= best and self.score > 0:
            self._pixel_text("NEW HIGH SCORE!", WIN_W // 2, 300, self.font_sm, COL_TURQ, center=True)
        self._make_btn(360, "RETRY", f"retry_{self.play_mode}")
        self._make_btn(415, "MENU", "title")
        self._draw_buttons()

    def _draw_highscores(self) -> None:
        th = self._theme()
        self._draw_bg_stars()
        self._pixel_text("HIGHSCORES", WIN_W // 2, 56, self.font_lg, th["accent"], center=True)
        y = 110
        for mode, label in (("classic", "CLASSIC"), ("speed", "SPEED")):
            self._pixel_text(label, 48, y, self.font_md, COL_GREEN)
            data = self.all_scores.get(mode, _empty_mode_scores())
            self._pixel_text(f"Best: {data.get('highscore', 0)}", 48, y + 28, self.font_sm, COL_TEXT)
            scores = list(data.get("scores", []))[:5]
            for i, sc in enumerate(scores):
                self._pixel_text(f"{i + 1}. {sc}", 64, y + 52 + i * 22, self.font_xs, COL_DIM)
            y += 200
        if not _web_profile():
            self._pixel_text("Synced to UsbGames profile", WIN_W // 2, 520, self.font_xs, COL_DIM, center=True)
        self._make_btn(560, "BACK", "title")
        self._draw_buttons()

    def _draw_settings(self) -> None:
        th = self._theme()
        self._draw_bg_stars()
        self._pixel_text("SETTINGS", WIN_W // 2, 56, self.font_lg, th["accent"], center=True)
        sfx = "ON" if self.settings.get("sfx", True) else "OFF"
        self._pixel_text(f"SFX: {sfx}", WIN_W // 2, 130, self.font_md, COL_TEXT, center=True)
        theme = self.settings.get("theme", "neon").upper()
        self._pixel_text(f"THEME: {theme}", WIN_W // 2, 180, self.font_md, COL_TEXT, center=True)
        self._pixel_text("Neon / Matrix / Violet palettes", WIN_W // 2, 220, self.font_xs, COL_DIM, center=True)
        self._make_btn(300, "TOGGLE SFX", "toggle_sfx")
        self._make_btn(355, "CYCLE THEME", "cycle_theme")
        self._make_btn(420, "BACK", "title")
        self._draw_buttons()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _save_settings(self) -> None:
        save_json(SETTINGS_PATH, self.settings)
        self.audio.sfx_on = self.settings.get("sfx", True)

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "modes":
            self.screen_id = Screen.MODE_SELECT
        elif action == "classic":
            self.start_game("classic")
        elif action == "speed":
            self.start_game("speed")
        elif action.startswith("retry_"):
            mode = action.split("_", 1)[1]
            self.start_game(mode)
        elif action == "highscores":
            self.all_scores = load_scores()
            self.screen_id = Screen.HIGHSCORES
        elif action == "settings":
            self.screen_id = Screen.SETTINGS
        elif action == "toggle_sfx":
            self.settings["sfx"] = not self.settings.get("sfx", True)
            self._save_settings()
        elif action == "cycle_theme":
            idx = THEME_NAMES.index(self.settings.get("theme", "neon"))
            self.settings["theme"] = THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
            self._save_settings()
        elif action == "title":
            self.screen_id = Screen.TITLE

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in self._keys_held:
                self._keys_held[event.key] = True
        if event.type == pygame.KEYUP:
            if event.key in self._keys_held:
                self._keys_held[event.key] = False

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
                return
            if self.screen_id == Screen.MODE_SELECT:
                self.start_game("classic")
                return
            if self.screen_id == Screen.GAME_OVER:
                act = f"retry_{self.play_mode}"
                self._do_action(act)
                return

        if self.screen_id == Screen.TITLE and event.key == pygame.K_p:
            self.screen_id = Screen.MODE_SELECT
            return

        if self.screen_id == Screen.PLAYING:
            if event.key in (pygame.K_UP, pygame.K_x):
                self._try_rotate()
            elif event.key == pygame.K_SPACE:
                self._hard_drop()
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if self._try_move(-1, 0):
                    self.audio.play(self.audio.move)
                    self._das_dir = -1
                    self._das_timer = 0.0
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if self._try_move(1, 0):
                    self.audio.play(self.audio.move)
                    self._das_dir = 1
                    self._das_timer = 0.0
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self._try_move(0, 1):
                    self.score += 1
                    self.audio.play(self.audio.move)

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
    BlockStackDXGame().run()


if __name__ == "__main__":
    main()
