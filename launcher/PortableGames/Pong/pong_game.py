#!/usr/bin/env python3
"""UsbGames Pong — retro paddle tennis arcade."""

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

GAME_ID = "Pong"
WIN_W, WIN_H = 480, 640
FPS_CAP = 60
HUD_H = 44
PADDLE_W, PADDLE_H = 14, 72
BALL_R = 8
WIN_SCORE = 11
SAMPLE_RATE = 22050

COL_BG = (10, 14, 22)
COL_TURQ = (64, 224, 208)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_BALL = (255, 230, 120)
COL_P1 = (64, 224, 208)
COL_P2 = (255, 120, 90)


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("pong",):
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
            self.paddle = _tone(320, 35, 0.2)
            self.wall = _tone(200, 25, 0.15)
            self.score = _tone(520, 80, 0.28)
            self.win = _tone(660, 120, 0.3)
            self.ui = _tone(480, 40, 0.2)
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


def load_stats() -> dict:
    default = {"wins_vs_ai": 0, "best_streak": 0, "scores": []}
    data = load_json(HIGHSCORE_LOCAL, default)
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            data["wins_vs_ai"] = max(int(data.get("wins_vs_ai", 0)), int(g.get("wins_vs_ai", 0)))
            data["best_streak"] = max(int(data.get("best_streak", 0)), int(g.get("best_streak", 0)))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


def save_stats(data: dict) -> None:
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
    MATCH_OVER = auto()
    SETTINGS = auto()


class PongGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Pong — UsbGames")
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
        self.stats = load_stats()

        self.screen_id = Screen.TITLE
        self.vs_ai = True
        self.score_l = 0
        self.score_r = 0
        self.streak = 0
        self.ball_x = WIN_W / 2
        self.ball_y = WIN_H / 2
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        self.paddle_l = WIN_H / 2
        self.paddle_r = WIN_H / 2
        self.serve_timer = 0.0
        self.serve_dir = 1
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

    def _make_btn(self, y: int, label: str, action: str, w: int = 220) -> None:
        self._buttons.append((pygame.Rect(WIN_W // 2 - w // 2, y, w, 38), label, action))

    def _draw_buttons(self) -> None:
        for rect, label, action in self._buttons:
            hover = self._hover == action
            pygame.draw.rect(self.screen, COL_BTN_HOVER if hover else COL_BTN, rect)
            pygame.draw.rect(self.screen, COL_TURQ if hover else COL_DIM, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 8, self.font_md, COL_TEXT, center=True)

    def _reset_ball(self, toward: int) -> None:
        self.ball_x = WIN_W / 2
        self.ball_y = WIN_H / 2
        angle = random.uniform(-0.45, 0.45)
        speed = 340.0
        self.ball_vx = math.cos(angle) * speed * toward
        self.ball_vy = math.sin(angle) * speed
        self.serve_timer = 0.6

    def start_match(self, vs_ai: bool) -> None:
        self.vs_ai = vs_ai
        self.score_l = 0
        self.score_r = 0
        self.streak = 0
        self.paddle_l = WIN_H / 2
        self.paddle_r = WIN_H / 2
        self.serve_dir = random.choice([-1, 1])
        self._reset_ball(self.serve_dir)
        self.screen_id = Screen.PLAYING

    def _score_point(self, left_scored: bool) -> None:
        self.audio.play(self.audio.score)
        if left_scored:
            self.score_l += 1
        else:
            self.score_r += 1
        if self.score_l >= WIN_SCORE or self.score_r >= WIN_SCORE:
            self._end_match()
            return
        self.serve_dir = -1 if left_scored else 1
        self._reset_ball(self.serve_dir)

    def _end_match(self) -> None:
        player_won = self.score_l >= WIN_SCORE
        if self.vs_ai and player_won:
            self.streak += 1
            self.stats["wins_vs_ai"] = int(self.stats.get("wins_vs_ai", 0)) + 1
            self.stats["best_streak"] = max(
                int(self.stats.get("best_streak", 0)), self.streak
            )
        elif self.vs_ai:
            self.streak = 0
        save_stats(self.stats)
        self.audio.play(self.audio.win)
        self.screen_id = Screen.MATCH_OVER

    def update(self, dt: float) -> None:
        if self.screen_id != Screen.PLAYING:
            return
        if self.serve_timer > 0:
            self.serve_timer -= dt
            return

        keys = pygame.key.get_pressed()
        speed = 420.0 * dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.paddle_l -= speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.paddle_l += speed
        self.paddle_l = max(HUD_H + PADDLE_H / 2, min(WIN_H - 40 - PADDLE_H / 2, self.paddle_l))

        if self.vs_ai:
            target = self.ball_y
            if self.ball_vx > 0:
                target += (self.paddle_r - target) * 0.15
            diff = target - self.paddle_r
            self.paddle_r += max(-speed * 0.92, min(speed * 0.92, diff))
        else:
            if keys[pygame.K_i]:
                self.paddle_r -= speed
            if keys[pygame.K_k]:
                self.paddle_r += speed
        self.paddle_r = max(HUD_H + PADDLE_H / 2, min(WIN_H - 40 - PADDLE_H / 2, self.paddle_r))

        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt

        if self.ball_y - BALL_R <= HUD_H + 8:
            self.ball_y = HUD_H + 8 + BALL_R
            self.ball_vy = abs(self.ball_vy)
            self.audio.play(self.audio.wall)
        if self.ball_y + BALL_R >= WIN_H - 36:
            self.ball_y = WIN_H - 36 - BALL_R
            self.ball_vy = -abs(self.ball_vy)
            self.audio.play(self.audio.wall)

        px_l = 28
        px_r = WIN_W - 28 - PADDLE_W
        pr_l = pygame.Rect(px_l, int(self.paddle_l - PADDLE_H / 2), PADDLE_W, PADDLE_H)
        pr_r = pygame.Rect(px_r, int(self.paddle_r - PADDLE_H / 2), PADDLE_W, PADDLE_H)
        ball_rect = pygame.Rect(int(self.ball_x - BALL_R), int(self.ball_y - BALL_R), BALL_R * 2, BALL_R * 2)

        if ball_rect.colliderect(pr_l) and self.ball_vx < 0:
            self.ball_x = pr_l.right + BALL_R
            hit = (self.ball_y - self.paddle_l) / (PADDLE_H / 2)
            self.ball_vx = abs(self.ball_vx) * 1.04
            self.ball_vy = hit * 380
            self.audio.play(self.audio.paddle)
        if ball_rect.colliderect(pr_r) and self.ball_vx > 0:
            self.ball_x = pr_r.left - BALL_R
            hit = (self.ball_y - self.paddle_r) / (PADDLE_H / 2)
            self.ball_vx = -abs(self.ball_vx) * 1.04
            self.ball_vy = hit * 380
            self.audio.play(self.audio.paddle)

        if self.ball_x < -BALL_R:
            self._score_point(False)
        elif self.ball_x > WIN_W + BALL_R:
            self._score_point(True)

        spd = math.hypot(self.ball_vx, self.ball_vy)
        if spd > 520:
            self.ball_vx *= 520 / spd
            self.ball_vy *= 520 / spd

    def draw(self) -> None:
        self.screen.fill(COL_BG)
        self._buttons.clear()

        if self.screen_id == Screen.TITLE:
            self._pixel_text("PONG", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
            self._pixel_text("UsbGames", WIN_W // 2, 150, self.font_sm, COL_DIM, center=True)
            wins = int(self.stats.get("wins_vs_ai", 0))
            self._pixel_text(f"AI WINS {wins}", WIN_W // 2, 210, self.font_md, COL_GREEN, center=True)
            self._make_btn(280, "PLAY", "modes")
            self._make_btn(335, "SETTINGS", "settings")
            self._draw_buttons()
            self._pixel_text("W/S — LEFT  ·  I/K — RIGHT (2P)", WIN_W // 2, WIN_H - 50, self.font_xs, COL_DIM, center=True)
        elif self.screen_id == Screen.MODE_SELECT:
            self._pixel_text("SELECT MODE", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
            self._make_btn(280, "VS CPU", "ai")
            self._make_btn(335, "2 PLAYERS", "two")
            self._make_btn(400, "BACK", "title")
            self._draw_buttons()
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED, Screen.MATCH_OVER):
            pygame.draw.line(self.screen, COL_DIM, (WIN_W // 2, HUD_H), (WIN_W // 2, WIN_H - 30), 2)
            for y in range(HUD_H + 20, WIN_H - 30, 28):
                pygame.draw.rect(self.screen, COL_DIM, (WIN_W // 2 - 2, y, 4, 14))
            self._pixel_text(str(self.score_l), WIN_W // 4, 12, self.font_md, COL_P1, center=True)
            self._pixel_text(str(self.score_r), 3 * WIN_W // 4, 12, self.font_md, COL_P2, center=True)
            pygame.draw.rect(
                self.screen, COL_P1,
                (28, int(self.paddle_l - PADDLE_H / 2), PADDLE_W, PADDLE_H),
            )
            pygame.draw.rect(
                self.screen, COL_P2,
                (WIN_W - 28 - PADDLE_W, int(self.paddle_r - PADDLE_H / 2), PADDLE_W, PADDLE_H),
            )
            pygame.draw.circle(self.screen, COL_BALL, (int(self.ball_x), int(self.ball_y)), BALL_R)
            if self.screen_id == Screen.PAUSED:
                ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 160))
                self.screen.blit(ov, (0, 0))
                self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2, self.font_lg, COL_TURQ, center=True)
            elif self.screen_id == Screen.MATCH_OVER:
                ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 175))
                self.screen.blit(ov, (0, 0))
                won = self.score_l >= WIN_SCORE
                msg = "YOU WIN!" if won else "CPU WINS" if self.vs_ai else "RIGHT WINS"
                if not self.vs_ai and won:
                    msg = "LEFT WINS"
                self._pixel_text(msg, WIN_W // 2, WIN_H // 2 - 30, self.font_lg, COL_GREEN, center=True)
                self._pixel_text(f"{self.score_l} — {self.score_r}", WIN_W // 2, WIN_H // 2 + 20, self.font_md, COL_TEXT, center=True)
                self._make_btn(WIN_H // 2 + 70, "REMATCH", "rematch")
                self._make_btn(WIN_H // 2 + 125, "MENU", "title")
                self._draw_buttons()
            elif self.serve_timer > 0:
                self._pixel_text("SERVE", WIN_W // 2, WIN_H // 2, self.font_md, COL_DIM, center=True)
        elif self.screen_id == Screen.SETTINGS:
            sfx = "ON" if self.settings.get("sfx", True) else "OFF"
            self._pixel_text("SETTINGS", WIN_W // 2, 56, self.font_lg, COL_TURQ, center=True)
            self._pixel_text(f"SFX: {sfx}", WIN_W // 2, 140, self.font_md, COL_TEXT, center=True)
            self._make_btn(300, "TOGGLE SFX", "toggle_sfx")
            self._make_btn(360, "BACK", "title")
            self._draw_buttons()

        _present_display(self._display, self.screen)

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "modes":
            self.screen_id = Screen.MODE_SELECT
        elif action == "ai":
            self.start_match(True)
        elif action == "two":
            self.start_match(False)
        elif action == "rematch":
            self.start_match(self.vs_ai)
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
            elif self.screen_id in (Screen.MODE_SELECT, Screen.SETTINGS, Screen.MATCH_OVER):
                self.screen_id = Screen.TITLE
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.screen_id == Screen.TITLE:
                self.screen_id = Screen.MODE_SELECT
            elif self.screen_id == Screen.MODE_SELECT:
                self.start_match(True)

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
    PongGame().run()


if __name__ == "__main__":
    main()
