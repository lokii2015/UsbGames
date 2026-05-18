#!/usr/bin/env python3
"""UsbGames Tic-Tac-Toe — retro pixel arcade."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GAME_ID = "TicTacToe"
EMPTY = 0
X_MARK = 1
O_MARK = 2

WIN_LINES = [
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    """UsbGames.exe folder when game lives in PortableGames/."""
    d = app_dir()
    if os.path.basename(d).lower() in ("tictactoe", "tic-tac-toe"):
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


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

WIN_W, WIN_H = 480, 520
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

GRID_PAD = 72
CELL = 108
GRID_OX = (WIN_W - 3 * CELL) // 2
GRID_OY = 148

COL_BG = (10, 12, 20)
COL_PANEL = (18, 22, 32)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 120, 112)
COL_WHITE = (245, 250, 255)
COL_TEXT = (210, 225, 230)
COL_DIM = (90, 100, 115)
COL_BTN = (24, 30, 42)
COL_BTN_HOVER = (36, 48, 58)
COL_BTN_BORDER = (64, 224, 208)
COL_WIN_LINE = (255, 220, 80)
COL_GRID = (40, 55, 70)
COL_CELL_HI = (28, 38, 52)

SAMPLE_RATE = 22050


def _tone(freq: float, ms: int, volume: float = 0.3) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * ms / 1000)
    amp = int(32767 * volume)
    buf = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        env = min(1.0, i / (n * 0.06), (n - i) / (n * 0.14))
        sample = int(amp * env * math.sin(2 * math.pi * freq * t))
        buf.extend(struct.pack("<h", sample))
    return pygame.mixer.Sound(buffer=bytes(buf))


class Audio:
    def __init__(self) -> None:
        self.enabled = True
        self.sfx_on = True
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.click = _tone(660, 35, 0.22)
            self.place = _tone(440, 50, 0.25)
            self.win = _tone(784, 120, 0.32)
            self.draw_snd = _tone(330, 150, 0.28)
        except pygame.error:
            self.enabled = False

    def play(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and self.sfx_on and snd:
            snd.play()


# ---------------------------------------------------------------------------
# Persistence / profile
# ---------------------------------------------------------------------------

DEFAULT_STATS = {
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "matches": 0,
    "ai_wins": 0,
    "ai_losses": 0,
    "ai_draws": 0,
    "pvp_matches": 0,
}


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


def load_stats() -> dict:
    stats = load_json(STATS_LOCAL, DEFAULT_STATS.copy())
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            game_stats = root.get("games", {}).get(GAME_ID, {})
            for k in DEFAULT_STATS:
                if k in game_stats:
                    stats[k] = max(int(stats.get(k, 0)), int(game_stats[k]))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return stats


def save_stats(stats: dict) -> None:
    save_json(STATS_LOCAL, stats)
    prof = profile_path()
    if not prof:
        return
    root = load_json(prof, {"profile": "default", "games": {}})
    if "games" not in root or not isinstance(root["games"], dict):
        root["games"] = {}
    root["games"][GAME_ID] = stats
    save_json(prof, root)


# ---------------------------------------------------------------------------
# AI (medium)
# ---------------------------------------------------------------------------


def find_line(board: List[int], mark: int) -> Optional[int]:
    for a, b, c in WIN_LINES:
        cells = [board[a], board[b], board[c]]
        if cells.count(mark) == 2 and EMPTY in cells:
            return [a, b, c][cells.index(EMPTY)]
    return None


def ai_move(board: List[int]) -> int:
    """Win > block > center > corner > random."""
    move = find_line(board, O_MARK)
    if move is not None:
        return move
    move = find_line(board, X_MARK)
    if move is not None:
        return move
    empties = [i for i, v in enumerate(board) if v == EMPTY]
    if 4 in empties:
        return 4
    corners = [i for i in empties if i in (0, 2, 6, 8)]
    if corners:
        return random.choice(corners)
    return random.choice(empties)


def check_winner(board: List[int]) -> Tuple[Optional[int], Optional[Tuple[int, int, int]]]:
    for line in WIN_LINES:
        a, b, c = line
        if board[a] and board[a] == board[b] == board[c]:
            return board[a], line
    if all(c != EMPTY for c in board):
        return 0, None
    return None, None


# ---------------------------------------------------------------------------
# Game modes & screens
# ---------------------------------------------------------------------------


class Mode(Enum):
    VS_AI = auto()
    VS_PLAYER = auto()


class Screen(Enum):
    TITLE = auto()
    MODE_SELECT = auto()
    PLAYING = auto()
    GAME_OVER = auto()
    SETTINGS = auto()


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class TicTacToeGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Tic-Tac-Toe — UsbGames")
        self._fullscreen = True
        self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 34, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True})
        self.audio.sfx_on = bool(self.settings.get("sfx", True))

        self.stats = load_stats()
        self.screen_id = Screen.TITLE
        self.mode = Mode.VS_AI
        self.board: List[int] = [EMPTY] * 9
        self.current = X_MARK
        self.winner: Optional[int] = None
        self.win_line: Optional[Tuple[int, int, int]] = None
        self.game_over_msg = ""
        self.cursor = 4
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._fade = 1.0
        self._fade_target = 1.0
        self._ai_thinking = False
        self._ai_timer = 0.0
        self._result_timer = 0.0

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

    def _cell_rect(self, idx: int) -> pygame.Rect:
        row, col = divmod(idx, 3)
        return pygame.Rect(
            GRID_OX + col * CELL,
            GRID_OY + row * CELL,
            CELL,
            CELL,
        )

    def _cell_at_pos(self, pos: Tuple[int, int]) -> Optional[int]:
        for i in range(9):
            if self._cell_rect(i).collidepoint(pos):
                return i
        return None

    def _reset_board(self) -> None:
        self.board = [EMPTY] * 9
        self.current = X_MARK
        self.winner = None
        self.win_line = None
        self.game_over_msg = ""
        self.cursor = 4
        self._ai_thinking = False
        self._result_timer = 0.0

    def _save_settings(self) -> None:
        save_json(SETTINGS_PATH, self.settings)

    def start_match(self) -> None:
        self._reset_board()
        self.screen_id = Screen.PLAYING
        self._fade_target = 1.0
    def _record_result(self, winner: Optional[int]) -> None:
        self.stats["matches"] = int(self.stats.get("matches", 0)) + 1
        if self.mode == Mode.VS_AI:
            if winner == X_MARK:
                self.stats["wins"] = int(self.stats.get("wins", 0)) + 1
                self.stats["ai_wins"] = int(self.stats.get("ai_wins", 0)) + 1
            elif winner == O_MARK:
                self.stats["losses"] = int(self.stats.get("losses", 0)) + 1
                self.stats["ai_losses"] = int(self.stats.get("ai_losses", 0)) + 1
            elif winner == 0:
                self.stats["draws"] = int(self.stats.get("draws", 0)) + 1
                self.stats["ai_draws"] = int(self.stats.get("ai_draws", 0)) + 1
        else:
            self.stats["pvp_matches"] = int(self.stats.get("pvp_matches", 0)) + 1
            if winner == X_MARK:
                self.stats["wins"] = int(self.stats.get("wins", 0)) + 1
            elif winner == O_MARK:
                self.stats["losses"] = int(self.stats.get("losses", 0)) + 1
            elif winner == 0:
                self.stats["draws"] = int(self.stats.get("draws", 0)) + 1
        save_stats(self.stats)

    def _place(self, idx: int) -> bool:
        if self.board[idx] != EMPTY or self.winner is not None:
            return False
        self.board[idx] = self.current
        self.audio.play(self.audio.place)
        winner, line = check_winner(self.board)
        if winner is not None:
            self.winner = winner
            self.win_line = line
            if winner == 0:
                self.game_over_msg = "DRAW"
                self.audio.play(self.audio.draw_snd)
            else:
                mark = "X" if winner == X_MARK else "O"
                if self.mode == Mode.VS_AI:
                    if winner == X_MARK:
                        self.game_over_msg = "YOU WIN!"
                        self.audio.play(self.audio.win)
                    elif winner == O_MARK:
                        self.game_over_msg = "YOU LOSE"
                        self.audio.play(self.audio.draw_snd)
                    else:
                        self.game_over_msg = f"{mark} WINS!"
                else:
                    self.game_over_msg = f"PLAYER {mark} WINS!"
                    self.audio.play(self.audio.win)
            self._record_result(winner)
            self._result_timer = 0.6
            return True
        self.current = O_MARK if self.current == X_MARK else X_MARK
        if self.mode == Mode.VS_AI and self.current == O_MARK:
            self._ai_thinking = True
            self._ai_timer = 0.35
        return True

    def _ai_turn(self) -> None:
        move = ai_move(self.board)
        self._place(move)

    def update(self, dt: float) -> None:
        self._fade += (self._fade_target - self._fade) * min(1.0, dt * 8)
        if self._ai_thinking:
            self._ai_timer -= dt
            if self._ai_timer <= 0:
                self._ai_thinking = False
                self._ai_turn()
        if self._result_timer > 0:
            self._result_timer -= dt
            if self._result_timer <= 0 and self.winner is not None:
                self.screen_id = Screen.GAME_OVER
                self._fade = 0.0
                self._fade_target = 1.0

    def _make_btn(self, y: int, label: str, action: str, w: int = 220, h: int = 38) -> None:
        self._buttons.append((pygame.Rect(WIN_W // 2 - w // 2, y, w, h), label, action))

    def _draw_btn(self) -> None:
        for rect, label, action in self._buttons:
            hover = self._hover == action
            pygame.draw.rect(self.screen, COL_BTN_HOVER if hover else COL_BTN, rect)
            border = COL_BTN_BORDER if hover else COL_DIM
            pygame.draw.rect(self.screen, border, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 8, self.font_md, COL_WHITE, center=True)

    def _draw_mark(self, idx: int, pulse: float = 0.0) -> None:
        rect = self._cell_rect(idx)
        cx, cy = rect.center
        mark = self.board[idx]
        if mark == X_MARK:
            off = 22 + int(pulse * 4)
            pygame.draw.line(self.screen, COL_TURQ, (cx - off, cy - off), (cx + off, cy + off), 5)
            pygame.draw.line(self.screen, COL_TURQ, (cx + off, cy - off), (cx - off, cy + off), 5)
        elif mark == O_MARK:
            r = 28 + int(pulse * 3)
            pygame.draw.circle(self.screen, COL_WHITE, (cx, cy), r, 5)

    def _draw_grid(self) -> None:
        for i in range(9):
            r = self._cell_rect(i)
            hi = i == self.cursor and self.screen_id == Screen.PLAYING
            pygame.draw.rect(self.screen, COL_CELL_HI if hi else COL_PANEL, r.inflate(-6, -6))
            if hi:
                pygame.draw.rect(self.screen, COL_TURQ_DIM, r.inflate(-6, -6), 2)
            if self.board[i]:
                self._draw_mark(i)
        # grid lines
        for i in range(1, 3):
            x = GRID_OX + i * CELL
            y = GRID_OY + i * CELL
            pygame.draw.line(self.screen, COL_GRID, (x, GRID_OY), (x, GRID_OY + 3 * CELL), 3)
            pygame.draw.line(self.screen, COL_GRID, (GRID_OX, y), (GRID_OX + 3 * CELL, y), 3)
        if self.win_line:
            pts = [self._cell_rect(i).center for i in self.win_line]
            pygame.draw.lines(self.screen, COL_WIN_LINE, False, pts, 6)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, 120))
        pygame.draw.line(self.screen, COL_TURQ, (0, 118), (WIN_W, 118), 2)
        if self.screen_id == Screen.PLAYING:
            if self.mode == Mode.VS_AI:
                turn = "YOUR TURN (X)" if self.current == X_MARK and not self._ai_thinking else "AI THINKING..."
                if self.winner:
                    turn = self.game_over_msg
            else:
                turn = f"PLAYER {'X' if self.current == X_MARK else 'O'} TURN"
            self._pixel_text(turn, WIN_W // 2, 24, self.font_md, COL_TURQ, center=True)
        m = int(self.stats.get("matches", 0))
        self._pixel_text(
            f"W{self.stats.get('wins', 0)} L{self.stats.get('losses', 0)} D{self.stats.get('draws', 0)}  ·  MATCH #{m}",
            WIN_W // 2,
            58,
            self.font_xs,
            COL_DIM,
            center=True,
        )
        mode_lbl = "VS AI" if self.mode == Mode.VS_AI else "2 PLAYER"
        self._pixel_text(mode_lbl, WIN_W // 2, 88, self.font_sm, COL_DIM, center=True)

    def draw(self) -> None:
        self.screen.fill(COL_BG)
        self._buttons.clear()
        alpha = int(255 * min(1.0, max(0.0, self._fade)))

        if self.screen_id == Screen.TITLE:
            self._draw_title()
        elif self.screen_id == Screen.MODE_SELECT:
            self._draw_mode_select()
        elif self.screen_id in (Screen.PLAYING, Screen.GAME_OVER):
            self._draw_hud()
            self._draw_grid()
            if self.screen_id == Screen.GAME_OVER:
                self._draw_game_over()
        elif self.screen_id == Screen.SETTINGS:
            self._draw_settings()

        if alpha < 255:
            fade = pygame.Surface((WIN_W, WIN_H))
            fade.fill(COL_BG)
            fade.set_alpha(255 - alpha)
            self.screen.blit(fade, (0, 0))

        _present_display(self._display, self.screen)

    def _draw_title(self) -> None:
        pygame.draw.rect(self.screen, COL_TURQ, (24, 28, WIN_W - 48, WIN_H - 56), 2)
        self._pixel_text("TIC-TAC-TOE", WIN_W // 2, 72, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames", WIN_W // 2, 112, self.font_sm, COL_DIM, center=True)
        self._make_btn(200, "PLAY", "play")
        self._make_btn(252, "MODE SELECT", "modes")
        self._make_btn(304, "SETTINGS", "settings")
        self._draw_btn()
        self._pixel_text("CLICK CELLS  ·  ARROWS + ENTER", WIN_W // 2, WIN_H - 40, self.font_xs, COL_DIM, center=True)

    def _draw_mode_select(self) -> None:
        pygame.draw.rect(self.screen, COL_TURQ, (24, 28, WIN_W - 48, WIN_H - 56), 2)
        self._pixel_text("MODE SELECT", WIN_W // 2, 60, self.font_lg, COL_TURQ, center=True)
        ai_sel = self.mode == Mode.VS_AI
        pvp_sel = self.mode == Mode.VS_PLAYER
        self._make_btn(130, "PLAY VS AI", "set_ai", w=260)
        if ai_sel:
            pygame.draw.rect(self.screen, COL_TURQ, self._buttons[-1][0].inflate(6, 6), 2)
        self._pixel_text("Medium AI · default", WIN_W // 2, 175, self.font_xs, COL_DIM, center=True)
        self._make_btn(220, "PLAY VS PLAYER", "set_pvp", w=260)
        if pvp_sel:
            pygame.draw.rect(self.screen, COL_TURQ, self._buttons[-1][0].inflate(6, 6), 2)
        self._pixel_text("Local same device", WIN_W // 2, 265, self.font_xs, COL_DIM, center=True)
        self._make_btn(340, "START GAME", "start")
        self._make_btn(395, "BACK", "title")
        self._draw_btn()

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text(self.game_over_msg or "GAME OVER", WIN_W // 2, 60, self.font_lg, COL_TURQ, center=True)
        self._make_btn(400, "RETRY", "retry")
        self._make_btn(455, "MENU", "title")
        self._draw_btn()

    def _settings_toggle_row(self, y: int, label: str, action: str, on: bool) -> None:
        self._pixel_text(label, 50, y + 10, self.font_sm, COL_TEXT)
        self._make_btn(y, "ON" if on else "OFF", action, w=90, h=34)
        self._buttons[-1] = (
            pygame.Rect(WIN_W - 125, y, 90, 34),
            "ON" if on else "OFF",
            action,
        )

    def _draw_settings(self) -> None:
        pygame.draw.rect(self.screen, COL_TURQ, (24, 28, WIN_W - 48, WIN_H - 56), 2)
        self._pixel_text("SETTINGS", WIN_W // 2, 60, self.font_lg, COL_TURQ, center=True)
        y = 120
        self._settings_toggle_row(y, "SOUND FX", "toggle_sfx", self.settings.get("sfx", True))
        y += 48
        self._pixel_text("S key toggles FX · ESC back", WIN_W // 2, y + 20, self.font_xs, COL_DIM, center=True)
        if not _web_profile():
            self._pixel_text("Profile stats sync to UsbGames/profiles/", WIN_W // 2, 280, self.font_xs, COL_DIM, center=True)
        self._make_btn(WIN_H - 88, "BACK", "title")
        self._draw_btn()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.click)
        if action == "play":
            self.start_match()
        elif action == "modes":
            self.screen_id = Screen.MODE_SELECT
            self._fade = 0.3
            self._fade_target = 1.0
        elif action == "settings":
            self.screen_id = Screen.SETTINGS
        elif action == "set_ai":
            self.mode = Mode.VS_AI
        elif action == "set_pvp":
            self.mode = Mode.VS_PLAYER
        elif action == "start":
            self.start_match()
        elif action == "retry":
            self.start_match()
        elif action == "title":
            self.screen_id = Screen.TITLE
            self._fade = 0.5
            self._fade_target = 1.0
        elif action.startswith("toggle_"):
            key = action[7:]
            self.settings[key] = not self.settings.get(key, True)
            if key == "sfx":
                self.audio.sfx_on = bool(self.settings["sfx"])
            self._save_settings()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mpos = _map_mouse(self._display, event.pos, WIN_W, WIN_H)
            act = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
            if act:
                self._do_action(act)
                return
            if self.screen_id == Screen.PLAYING and not self._ai_thinking and self.winner is None:
                idx = self._cell_at_pos(event.pos)
                if idx is not None and self._can_play_cell(idx):
                    self._place(idx)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.screen_id == Screen.SETTINGS:
            if event.key == pygame.K_F11:
                self._fullscreen = not self._fullscreen
                self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self._fullscreen else pygame.display.set_mode((WIN_W, WIN_H))
                return
            if event.key == pygame.K_ESCAPE:
                self.screen_id = Screen.TITLE
                return
            if event.key == pygame.K_s:
                self._do_action("toggle_sfx")
                return
            return
        if event.key == pygame.K_F11:
            self._fullscreen = not self._fullscreen
            self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self._fullscreen else pygame.display.set_mode((WIN_W, WIN_H))
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.TITLE
            elif self.screen_id in (Screen.MODE_SELECT, Screen.SETTINGS, Screen.GAME_OVER):
                self.screen_id = Screen.TITLE
            return
        if self.screen_id == Screen.TITLE and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.start_match()
            self.audio.play(self.audio.click)
        if self.screen_id == Screen.PLAYING and self.winner is None and not self._ai_thinking:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                if self.cursor % 3 > 0:
                    self.cursor -= 1
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if self.cursor % 3 < 2:
                    self.cursor += 1
            elif event.key in (pygame.K_UP, pygame.K_w):
                if self.cursor >= 3:
                    self.cursor -= 3
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.cursor < 6:
                    self.cursor += 3
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._can_play_cell(self.cursor):
                    self._place(self.cursor)

    def _can_play_cell(self, idx: int) -> bool:
        if self.board[idx] != EMPTY:
            return False
        if self.mode == Mode.VS_AI and self.current != X_MARK:
            return False
        return True

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
    TicTacToeGame().run()


if __name__ == "__main__":
    main()
