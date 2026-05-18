#!/usr/bin/env python3
"""UsbGames Memory Match — flip cards and find matching pairs."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame

GAME_ID = "MemoryMatch"

WIN_W, WIN_H = 480, 640
FPS_CAP = 60

def _present_display(_display, _canvas):
    sw, sh = _display.get_size()
    cw, ch = _canvas.get_size()
    if sw == cw and sh == ch:
        _display.blit(_canvas, (0, 0))
    else:
        _display.blit(pygame.transform.smoothscale(_canvas, (sw, sh)), (0, 0))
    _present_display(self._display, self.screen)

def _map_mouse(_display, pos, lw, lh):
    sw, sh = _display.get_size()
    if sw <= 0 or sh <= 0:
        return pos
    return int(pos[0] * lw / sw), int(pos[1] * lh / sh)

HUD_H = 44

COL_BG = (10, 14, 22)
COL_BG2 = (14, 20, 32)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 140, 128)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_CARD_BACK = (28, 36, 52)
COL_CARD_EDGE = (64, 224, 208)

SAMPLE_RATE = 22050

DIFFICULTIES = {
    "easy": (4, 3),
    "medium": (4, 4),
    "hard": (4, 5),
}

# pair_id -> (fill color, label)
SYMBOLS: List[Tuple[Tuple[int, int, int], str]] = [
    ((255, 90, 90), "★"),
    ((255, 160, 60), "◆"),
    ((255, 220, 80), "●"),
    ((100, 220, 140), "▲"),
    ((64, 200, 255), "■"),
    ((180, 120, 255), "♥"),
    ((64, 224, 208), "✦"),
    ((255, 120, 180), "☀"),
    ((200, 200, 220), "☽"),
    ((57, 255, 120), "⚡"),
]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("memorymatch", "memory-match", "memory match"):
        parent = os.path.dirname(d)
        if os.path.basename(parent).lower() == "portablegames":
            return os.path.dirname(parent)
    return None


STATS_LOCAL = os.path.join(app_dir(), "stats.json")
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
            self.flip = _tone(420, 35, 0.18)
            self.match = _tone(720, 80, 0.24)
            self.miss = _tone(180, 90, 0.22)
            self.win = _tone(880, 120, 0.26)
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


def default_stats() -> dict:
    return {
        "games_played": 0,
        "games_won": 0,
        "best_moves": {"easy": 0, "medium": 0, "hard": 0},
        "best_time": {"easy": 0.0, "medium": 0.0, "hard": 0.0},
    }


def load_stats() -> dict:
    data = load_json(STATS_LOCAL, default_stats())
    for key in ("best_moves", "best_time"):
        if key not in data or not isinstance(data[key], dict):
            data[key] = default_stats()[key]
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            for diff in ("easy", "medium", "hard"):
                bt = g.get("best_time", {}).get(diff)
                if bt and (data["best_time"].get(diff) in (0, 0.0) or bt < data["best_time"][diff]):
                    data["best_time"][diff] = float(bt)
                bm = g.get("best_moves", {}).get(diff)
                if bm and (not data["best_moves"].get(diff) or bm < data["best_moves"][diff]):
                    data["best_moves"][diff] = int(bm)
            data["games_won"] = max(data.get("games_won", 0), int(g.get("games_won", 0)))
            data["games_played"] = max(data.get("games_played", 0), int(g.get("games_played", 0)))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


def save_stats(data: dict) -> None:
    save_json(STATS_LOCAL, data)
    prof = profile_path()
    if not prof:
        return
    root = load_json(prof, {"profile": "default", "games": {}})
    if "games" not in root or not isinstance(root["games"], dict):
        root["games"] = {}
    root["games"][GAME_ID] = data
    save_json(prof, root)


@dataclass
class Card:
    pair_id: int
    rect: pygame.Rect
    face_up: bool = False
    matched: bool = False
    flip_t: float = 0.0


class Screen(Enum):
    TITLE = auto()
    PLAYING = auto()
    WIN = auto()


class MemoryMatchGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Memory Match — UsbGames")
        self._fullscreen = True
        self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 32, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)
        self.symbol_font = pygame.font.SysFont("segoeuisymbol", 28, bold=True)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True})
        self.audio.sfx_on = self.settings.get("sfx", True)

        self.stats = load_stats()
        self.screen_id = Screen.TITLE
        self.difficulty = "easy"
        self.cards: List[Card] = []
        self.first_pick: Optional[int] = None
        self.moves = 0
        self.elapsed = 0.0
        self.lock_input = False
        self.hide_timer = 0.0
        self._pending_hide: Tuple[int, int] = (-1, -1)
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._grid: Tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)

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

    def _build_grid(self) -> None:
        cols, rows = DIFFICULTIES[self.difficulty]
        pairs = (cols * rows) // 2
        ids = list(range(pairs))
        deck = ids + ids
        random.shuffle(deck)

        margin_x, margin_y = 20, HUD_H + 16
        gap = 8
        avail_w = WIN_W - margin_x * 2 - gap * (cols - 1)
        avail_h = WIN_H - margin_y - 24 - gap * (rows - 1)
        cw = avail_w // cols
        ch = avail_h // rows
        card_size = min(cw, ch, 88)

        self.cards.clear()
        idx = 0
        grid_w = cols * card_size + gap * (cols - 1)
        grid_h = rows * card_size + gap * (rows - 1)
        start_x = (WIN_W - grid_w) // 2
        start_y = margin_y + (WIN_H - margin_y - grid_h) // 2 - 10

        for row in range(rows):
            for col in range(cols):
                x = start_x + col * (card_size + gap)
                y = start_y + row * (card_size + gap)
                self.cards.append(
                    Card(
                        pair_id=deck[idx],
                        rect=pygame.Rect(x, y, card_size, card_size),
                    )
                )
                idx += 1

        self._grid = (cols, rows, card_size, start_x, start_y)

    def start_game(self, difficulty: str) -> None:
        self.difficulty = difficulty
        self.moves = 0
        self.elapsed = 0.0
        self.first_pick = None
        self.lock_input = False
        self.hide_timer = 0.0
        self._build_grid()
        self.screen_id = Screen.PLAYING
        st = load_stats()
        st["games_played"] = int(st.get("games_played", 0)) + 1
        save_stats(st)
        self.stats = load_stats()

    def _all_matched(self) -> bool:
        return bool(self.cards) and all(c.matched for c in self.cards)

    def _win(self) -> None:
        self.audio.play(self.audio.win)
        self.screen_id = Screen.WIN
        st = load_stats()
        st["games_won"] = int(st.get("games_won", 0)) + 1
        diff = self.difficulty
        bt = st["best_time"].get(diff, 0.0)
        if bt in (0, 0.0) or self.elapsed < bt:
            st["best_time"][diff] = round(self.elapsed, 1)
        bm = st["best_moves"].get(diff, 0)
        if not bm or self.moves < bm:
            st["best_moves"][diff] = self.moves
        save_stats(st)
        self.stats = load_stats()

    def _pick_card(self, index: int) -> None:
        card = self.cards[index]
        if card.matched or card.face_up or self.lock_input:
            return
        card.face_up = True
        card.flip_t = 0.0
        self.audio.play(self.audio.flip)

        if self.first_pick is None:
            self.first_pick = index
            return

        if self.first_pick == index:
            return

        self.moves += 1
        a = self.cards[self.first_pick]
        if a.pair_id == card.pair_id:
            a.matched = True
            card.matched = True
            self.first_pick = None
            self.audio.play(self.audio.match)
            if self._all_matched():
                self._win()
        else:
            self.lock_input = True
            self._pending_hide = (self.first_pick, index)
            self.hide_timer = 0.65
            self.first_pick = None
            self.audio.play(self.audio.miss)

    def _card_at(self, pos: Tuple[int, int]) -> Optional[int]:
        for i, card in enumerate(self.cards):
            if card.rect.collidepoint(pos):
                return i
        return None

    def update(self, dt: float) -> None:
        if self.screen_id == Screen.PLAYING:
            self.elapsed += dt
            for card in self.cards:
                if card.face_up or card.matched:
                    card.flip_t = min(1.0, card.flip_t + dt * 6)
                else:
                    card.flip_t = max(0.0, card.flip_t - dt * 6)

            if self.hide_timer > 0:
                self.hide_timer -= dt
                if self.hide_timer <= 0:
                    i, j = self._pending_hide
                    if 0 <= i < len(self.cards):
                        self.cards[i].face_up = False
                    if 0 <= j < len(self.cards):
                        self.cards[j].face_up = False
                    self.lock_input = False

    def _draw_card_back(self, rect: pygame.Rect, highlight: bool = False) -> None:
        pygame.draw.rect(self.screen, COL_CARD_BACK, rect, border_radius=6)
        edge = COL_TURQ if highlight else COL_TURQ_DIM
        pygame.draw.rect(self.screen, edge, rect, 2, border_radius=6)
        pygame.draw.rect(self.screen, COL_TURQ_DIM, rect.inflate(-12, -12), 1, border_radius=4)
        cx, cy = rect.center
        self._pixel_text("?", cx, cy - 8, self.font_md, COL_TURQ_DIM, center=True)

    def _draw_card_face(self, card: Card) -> None:
        rect = card.rect
        color, label = SYMBOLS[card.pair_id % len(SYMBOLS)]
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        inner = rect.inflate(-8, -8)
        pygame.draw.rect(self.screen, tuple(min(255, c + 30) for c in color), inner, border_radius=4)
        pygame.draw.rect(self.screen, COL_CARD_EDGE, rect, 2, border_radius=6)
        surf = self.symbol_font.render(label, True, (255, 255, 255))
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def _draw_card(self, card: Card) -> None:
        show_face = card.matched or (card.face_up and card.flip_t > 0.5)
        if show_face:
            self._draw_card_face(card)
        else:
            self._draw_card_back(card.rect, card.face_up and card.flip_t > 0.3)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        mins = int(self.elapsed) // 60
        secs = int(self.elapsed) % 60
        self._pixel_text(f"{mins:01d}:{secs:02d}", 12, 8, self.font_sm, COL_TEXT)
        self._pixel_text(self.difficulty.upper(), WIN_W // 2, 8, self.font_sm, COL_TURQ, center=True)
        surf = self.font_sm.render(f"MOVES {self.moves}", True, COL_TEXT)
        self.screen.blit(surf, (WIN_W - surf.get_width() - 12, 8))

    def _make_btn(self, y: int, label: str, action: str, w: int = 200) -> None:
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
            self._draw_title()
        elif self.screen_id == Screen.PLAYING:
            self._draw_play()
        elif self.screen_id == Screen.WIN:
            self._draw_play()
            self._draw_win()
        _present_display(self._display, self.screen)

    def _draw_title(self) -> None:
        for y in range(0, WIN_H, 40):
            shade = COL_BG if (y // 40) % 2 == 0 else COL_BG2
            pygame.draw.rect(self.screen, shade, (0, y, WIN_W, 40))
        pygame.draw.rect(self.screen, COL_TURQ, (24, 48, WIN_W - 48, WIN_H - 56), 2)
        self._pixel_text("MEMORY MATCH", WIN_W // 2, 72, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames", WIN_W // 2, 112, self.font_sm, COL_DIM, center=True)
        won = int(self.stats.get("games_won", 0))
        self._pixel_text(f"WINS {won}", WIN_W // 2, 148, self.font_sm, COL_GREEN, center=True)

        self._make_btn(210, "EASY  (4×3)", "easy", 220)
        self._make_btn(262, "MEDIUM (4×4)", "medium", 220)
        self._make_btn(314, "HARD  (4×5)", "hard", 220)
        self._draw_buttons()

        y = 380
        for diff, label in (("easy", "Easy"), ("medium", "Med"), ("hard", "Hard")):
            bt = self.stats.get("best_time", {}).get(diff, 0)
            bm = self.stats.get("best_moves", {}).get(diff, 0)
            if bt:
                txt = f"{label}: {bt:.1f}s · {bm} moves"
            else:
                txt = f"{label}: —"
            self._pixel_text(txt, WIN_W // 2, y, self.font_xs, COL_DIM, center=True)
            y += 22

        self._pixel_text("CLICK CARDS TO FLIP & MATCH", WIN_W // 2, WIN_H - 48, self.font_xs, COL_DIM, center=True)

    def _draw_play(self) -> None:
        for y in range(HUD_H, WIN_H, 40):
            shade = COL_BG if ((y - HUD_H) // 40) % 2 == 0 else COL_BG2
            pygame.draw.rect(self.screen, shade, (0, y, WIN_W, 40))
        for card in self.cards:
            self._draw_card(card)
        self._draw_hud()

    def _draw_win(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("YOU WIN!", WIN_W // 2, 160, self.font_lg, COL_GREEN, center=True)
        mins = int(self.elapsed) // 60
        secs = int(self.elapsed) % 60
        self._pixel_text(f"TIME {mins:01d}:{secs:02d}", WIN_W // 2, 220, self.font_md, COL_TEXT, center=True)
        self._pixel_text(f"MOVES {self.moves}", WIN_W // 2, 260, self.font_md, COL_TEXT, center=True)
        bt = self.stats.get("best_time", {}).get(self.difficulty, 0)
        if bt:
            self._pixel_text(f"BEST {bt:.1f}s", WIN_W // 2, 300, self.font_sm, COL_TURQ, center=True)
        self._make_btn(360, "PLAY AGAIN", "again")
        self._make_btn(415, "MENU", "title")
        self._draw_buttons()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action in ("easy", "medium", "hard"):
            self.start_game(action)
        elif action == "again":
            self.start_game(self.difficulty)
        elif action == "title":
            self.stats = load_stats()
            self.screen_id = Screen.TITLE

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mpos = _map_mouse(self._display, event.pos, WIN_W, WIN_H)
            act = self._hit_btn(mpos)
            if act:
                self._do_action(act)
                return
            if self.screen_id == Screen.PLAYING:
                idx = self._card_at(mpos)
                if idx is not None:
                    self._pick_card(idx)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
            self._fullscreen = not self._fullscreen
            self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self._fullscreen else pygame.display.set_mode((WIN_W, WIN_H))
            return
        if event.key == pygame.K_ESCAPE:
                if self.screen_id == Screen.PLAYING:
                    self.stats = load_stats()
                    self.screen_id = Screen.TITLE
                elif self.screen_id == Screen.WIN:
                    self.screen_id = Screen.TITLE

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS_CAP) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()


def main() -> None:
    MemoryMatchGame().run()


if __name__ == "__main__":
    main()
