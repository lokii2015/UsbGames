#!/usr/bin/env python3
"""UsbGames Brick Breaker — retro paddle & ball arcade."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame

GAME_ID = "BrickBreaker"

WIN_W, WIN_H = 480, 640
FPS_CAP = 60


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


HUD_H = 44
PADDLE_W = 88
PADDLE_H = 12
PADDLE_Y = WIN_H - 48
BALL_R = 7
BRICK_ROWS = 7
BRICK_COLS = 10
BRICK_PAD = 4
BRICK_TOP = HUD_H + 28
PLAY_BOTTOM = PADDLE_Y - 8

COL_BG = (10, 14, 22)
COL_BG2 = (14, 20, 32)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 140, 128)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_BALL = (255, 230, 120)
COL_PADDLE = (64, 224, 208)

BRICK_COLORS = [
    ((255, 90, 90), 50),
    ((255, 160, 60), 40),
    ((255, 220, 80), 30),
    ((100, 220, 140), 25),
    ((64, 200, 255), 20),
    ((180, 120, 255), 15),
    ((64, 224, 208), 10),
]

SAMPLE_RATE = 22050
BASE_BALL_SPEED = 320.0


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("brickbreaker", "brick-breaker", "brick breaker"):
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
            self.brick = _tone(440, 45, 0.22)
            self.paddle = _tone(280, 35, 0.2)
            self.wall = _tone(200, 30, 0.15)
            self.life = _tone(150, 120, 0.3)
            self.level = _tone(660, 90, 0.28)
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


def load_highscore() -> Tuple[int, List[int]]:
    data = load_json(HIGHSCORE_LOCAL, {"highscore": 0, "scores": []})
    hs = int(data.get("highscore", 0))
    scores = list(data.get("scores", []))[:10]
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            hs = max(hs, int(g.get("highscore", 0)))
            prof_scores = g.get("scores", [])
            if isinstance(prof_scores, list):
                merged = sorted(set(scores + [int(x) for x in prof_scores]), reverse=True)[:10]
                scores = merged
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return hs, scores


def save_highscore(highscore: int, scores: List[int]) -> None:
    payload = {"highscore": highscore, "scores": scores[:10]}
    save_json(HIGHSCORE_LOCAL, payload)
    prof = profile_path()
    if not prof:
        return
    root = load_json(prof, {"profile": "default", "games": {}})
    if "games" not in root or not isinstance(root["games"], dict):
        root["games"] = {}
    root["games"][GAME_ID] = payload
    save_json(prof, root)


@dataclass
class Brick:
    rect: pygame.Rect
    color: Tuple[int, int, int]
    points: int
    alive: bool = True


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    stuck: bool = True

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R * 2, BALL_R * 2)


class Screen(Enum):
    TITLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    LEVEL_CLEAR = auto()
    GAME_OVER = auto()


class BrickBreakerGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Brick Breaker — UsbGames")
        self._fullscreen = True
        self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 32, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True})
        self.audio.sfx_on = self.settings.get("sfx", True)

        self.highscore, self.score_history = load_highscore()
        self.screen_id = Screen.TITLE
        self.score = 0
        self.level = 1
        self.lives = 3
        self.paddle_x = WIN_W / 2 - PADDLE_W / 2
        self.paddle_w = PADDLE_W
        self.balls: List[Ball] = []
        self.bricks: List[Brick] = []
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._level_timer = 0.0
        self._launch_cooldown = 0.0
        self._keys = {pygame.K_LEFT: False, pygame.K_RIGHT: False, pygame.K_a: False, pygame.K_d: False}

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

    def _brick_grid(self) -> Tuple[int, int, int]:
        margin = 16
        avail = WIN_W - margin * 2
        bw = (avail - BRICK_PAD * (BRICK_COLS - 1)) // BRICK_COLS
        bh = 22
        return bw, bh, margin

    def _build_level(self) -> None:
        self.bricks.clear()
        bw, bh, margin = self._brick_grid()
        pattern_seed = self.level * 17 + 3
        rng = random.Random(pattern_seed)
        for row in range(BRICK_ROWS):
            color, pts = BRICK_COLORS[min(row, len(BRICK_COLORS) - 1)]
            for col in range(BRICK_COLS):
                if rng.random() < 0.08 + row * 0.02:
                    continue
                x = margin + col * (bw + BRICK_PAD)
                y = BRICK_TOP + row * (bh + BRICK_PAD)
                self.bricks.append(
                    Brick(
                        rect=pygame.Rect(x, y, bw, bh),
                        color=color,
                        points=pts + self.level * 2,
                    )
                )

    def _reset_ball(self, stick: bool = True) -> None:
        self.balls = [
            Ball(
                x=self.paddle_x + self.paddle_w / 2,
                y=PADDLE_Y - BALL_R - 2,
                vx=0.0,
                vy=0.0,
                stuck=stick,
            )
        ]

    def _ball_speed(self) -> float:
        return BASE_BALL_SPEED + (self.level - 1) * 28

    def _launch_ball(self, ball: Ball) -> None:
        if not ball.stuck:
            return
        angle = random.uniform(-0.65, 0.65)
        speed = self._ball_speed()
        ball.vx = math.sin(angle) * speed
        ball.vy = -math.cos(angle) * speed
        ball.stuck = False
        self.audio.play(self.audio.ui)

    def start_game(self) -> None:
        self.score = 0
        self.level = 1
        self.lives = 3
        self.paddle_w = PADDLE_W
        self.paddle_x = WIN_W / 2 - self.paddle_w / 2
        self._build_level()
        self._reset_ball(True)
        self.screen_id = Screen.PLAYING
        self._launch_cooldown = 0.3

    def _next_level(self) -> None:
        self.level += 1
        self._build_level()
        self._reset_ball(True)
        self._launch_cooldown = 0.5
        self.screen_id = Screen.LEVEL_CLEAR
        self._level_timer = 1.8
        self.audio.play(self.audio.level)

    def _lose_life(self) -> None:
        self.audio.play(self.audio.life)
        self.lives -= 1
        if self.lives <= 0:
            self._game_over()
            return
        self.paddle_x = WIN_W / 2 - self.paddle_w / 2
        self._reset_ball(True)
        self._launch_cooldown = 0.6

    def _game_over(self) -> None:
        if self.score > self.highscore:
            self.highscore = self.score
        self.score_history.insert(0, self.score)
        self.score_history = sorted(set(self.score_history), reverse=True)[:10]
        save_highscore(self.highscore, self.score_history)
        self.screen_id = Screen.GAME_OVER

    def _resolve_brick_hit(self, ball: Ball, brick: Brick) -> None:
        brick.alive = False
        self.score += brick.points
        self.audio.play(self.audio.brick)

        dx = (ball.x - brick.rect.centerx) / max(brick.rect.width / 2, 1)
        dy = (ball.y - brick.rect.centery) / max(brick.rect.height / 2, 1)
        if abs(dx) > abs(dy):
            ball.vx *= -1
        else:
            ball.vy *= -1

    def _paddle_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.paddle_x), PADDLE_Y, int(self.paddle_w), PADDLE_H)

    def update(self, dt: float) -> None:
        if self.screen_id == Screen.LEVEL_CLEAR:
            self._level_timer -= dt
            if self._level_timer <= 0:
                self.screen_id = Screen.PLAYING
            return

        if self.screen_id != Screen.PLAYING:
            return

        if self._launch_cooldown > 0:
            self._launch_cooldown -= dt

        speed = 420.0
        if self._keys[pygame.K_LEFT] or self._keys[pygame.K_a]:
            self.paddle_x -= speed * dt
        if self._keys[pygame.K_RIGHT] or self._keys[pygame.K_d]:
            self.paddle_x += speed * dt
        self.paddle_x = max(8, min(WIN_W - self.paddle_w - 8, self.paddle_x))

        paddle = self._paddle_rect()
        alive_bricks = [b for b in self.bricks if b.alive]

        for ball in self.balls:
            if ball.stuck:
                ball.x = self.paddle_x + self.paddle_w / 2
                ball.y = PADDLE_Y - BALL_R - 2
                continue

            ball.x += ball.vx * dt
            ball.y += ball.vy * dt
            br = ball.rect()

            if ball.x <= BALL_R or ball.x >= WIN_W - BALL_R:
                ball.vx *= -1
                ball.x = max(BALL_R, min(WIN_W - BALL_R, ball.x))
                self.audio.play(self.audio.wall)
            if ball.y <= HUD_H + BALL_R:
                ball.vy *= -1
                ball.y = HUD_H + BALL_R
                self.audio.play(self.audio.wall)

            if ball.y > WIN_H + 20:
                continue

            if br.colliderect(paddle) and ball.vy > 0:
                hit = (ball.x - paddle.centerx) / (self.paddle_w / 2)
                hit = max(-1.0, min(1.0, hit))
                spd = math.hypot(ball.vx, ball.vy)
                spd = max(spd, self._ball_speed() * 0.85)
                angle = hit * 0.75
                ball.vx = math.sin(angle) * spd
                ball.vy = -abs(math.cos(angle) * spd)
                ball.y = PADDLE_Y - BALL_R - 1
                self.audio.play(self.audio.paddle)

            for brick in alive_bricks:
                if brick.alive and br.colliderect(brick.rect):
                    self._resolve_brick_hit(ball, brick)
                    break

        self.balls = [b for b in self.balls if b.y <= WIN_H + 30]
        if not self.balls:
            self._lose_life()
            return

        if not any(b.alive for b in self.bricks):
            self._next_level()

    def _draw_bg(self) -> None:
        for y in range(HUD_H, WIN_H, 40):
            shade = COL_BG if ((y - HUD_H) // 40) % 2 == 0 else COL_BG2
            pygame.draw.rect(self.screen, shade, (0, y, WIN_W, 40))

    def _draw_bricks(self) -> None:
        for brick in self.bricks:
            if not brick.alive:
                continue
            pygame.draw.rect(self.screen, brick.color, brick.rect)
            inner = brick.rect.inflate(-4, -4)
            pygame.draw.rect(self.screen, tuple(min(255, c + 40) for c in brick.color), inner)
            pygame.draw.rect(self.screen, COL_TURQ_DIM, brick.rect, 1)

    def _draw_paddle(self) -> None:
        r = self._paddle_rect()
        pygame.draw.rect(self.screen, COL_PADDLE, r, border_radius=3)
        pygame.draw.rect(self.screen, COL_TURQ, r, 2, border_radius=3)
        pygame.draw.rect(self.screen, (255, 255, 255), (r.centerx - 8, r.top + 3, 16, 3))

    def _draw_ball(self, ball: Ball) -> None:
        pygame.draw.circle(self.screen, COL_BALL, (int(ball.x), int(ball.y)), BALL_R)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(ball.x) - 2, int(ball.y) - 2), 2)

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
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED, Screen.LEVEL_CLEAR):
            self._draw_play()
            if self.screen_id == Screen.PAUSED:
                self._draw_pause()
            elif self.screen_id == Screen.LEVEL_CLEAR:
                self._draw_level_banner()
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_play(frozen=True)
            self._draw_game_over()

        _present_display(self._display, self.screen)

    def _draw_title(self) -> None:
        self._draw_bg()
        pygame.draw.rect(self.screen, COL_TURQ, (24, 56, WIN_W - 48, WIN_H - 100), 2)
        self._pixel_text("BRICK BREAKER", WIN_W // 2, 110, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames", WIN_W // 2, 155, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"HIGH SCORE {self.highscore}", WIN_W // 2, 200, self.font_md, COL_GREEN, center=True)
        self._draw_title_preview()
        self._make_btn(360, "PLAY", "play")
        self._draw_buttons()
        self._pixel_text("ARROWS / A D — MOVE PADDLE", WIN_W // 2, WIN_H - 72, self.font_xs, COL_DIM, center=True)
        self._pixel_text("SPACE — LAUNCH BALL", WIN_W // 2, WIN_H - 52, self.font_xs, COL_DIM, center=True)
        self._pixel_text("F11 — WINDOWED", WIN_W // 2, WIN_H - 32, self.font_xs, COL_DIM, center=True)

    def _draw_title_preview(self) -> None:
        cx, cy = WIN_W // 2, 290
        for i, (col, _) in enumerate(BRICK_COLORS[:4]):
            pygame.draw.rect(self.screen, col, (cx - 90 + i * 48, cy - 40, 40, 16))
        pygame.draw.rect(self.screen, COL_PADDLE, (cx - 44, cy + 30, 88, 10))
        pygame.draw.circle(self.screen, COL_BALL, (cx, cy + 10), 6)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        self._pixel_text(f"SCORE {self.score}", 12, 8, self.font_sm, COL_TEXT)
        self._pixel_text(f"LV {self.level}", WIN_W // 2, 8, self.font_sm, COL_TURQ, center=True)
        hearts = "♥" * self.lives + "♡" * max(0, 3 - self.lives)
        surf = self.font_sm.render(hearts, True, (255, 90, 90))
        self.screen.blit(surf, (WIN_W - surf.get_width() - 12, 8))

    def _draw_play(self, frozen: bool = False) -> None:
        self._draw_bg()
        self._draw_bricks()
        self._draw_paddle()
        for ball in self.balls:
            self._draw_ball(ball)
        self._draw_hud()
        if not frozen and self.balls and self.balls[0].stuck and self._launch_cooldown <= 0:
            self._pixel_text("SPACE TO LAUNCH", WIN_W // 2, WIN_H // 2, self.font_xs, COL_DIM, center=True)

    def _draw_pause(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2 - 20, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("ESC — RESUME", WIN_W // 2, WIN_H // 2 + 24, self.font_xs, COL_DIM, center=True)

    def _draw_level_banner(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text(f"LEVEL {self.level}", WIN_W // 2, WIN_H // 2 - 16, self.font_lg, COL_GREEN, center=True)

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("GAME OVER", WIN_W // 2, 150, self.font_lg, COL_TURQ, center=True)
        self._pixel_text(f"SCORE {self.score}", WIN_W // 2, 205, self.font_md, COL_TEXT, center=True)
        self._pixel_text(f"LEVEL {self.level}", WIN_W // 2, 240, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"BEST {self.highscore}", WIN_W // 2, 275, self.font_sm, COL_GREEN, center=True)
        if self.score >= self.highscore and self.score > 0:
            self._pixel_text("NEW HIGH SCORE!", WIN_W // 2, 310, self.font_sm, COL_TURQ, center=True)
        self._make_btn(360, "RETRY", "retry")
        self._make_btn(415, "MENU", "title")
        self._draw_buttons()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action in ("play", "retry"):
            self.start_game()
        elif action == "title":
            self.screen_id = Screen.TITLE

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(_map_mouse(self._display, event.pos, WIN_W, WIN_H))
        if event.type == pygame.KEYDOWN:
            if event.key in self._keys:
                self._keys[event.key] = True
        if event.type == pygame.KEYUP:
            if event.key in self._keys:
                self._keys[event.key] = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mpos = _map_mouse(self._display, event.pos, WIN_W, WIN_H)
            act = self._hit_btn(mpos)
            if act:
                self._do_action(act)
                return
            if self.screen_id == Screen.TITLE:
                self.start_game()
            elif self.screen_id == Screen.PLAYING and self.balls:
                self._launch_ball(self.balls[0])
            elif self.screen_id == Screen.GAME_OVER:
                self.start_game()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_F11:
            self._fullscreen = not self._fullscreen
            if self._fullscreen:
                self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            else:
                self._display = pygame.display.set_mode((WIN_W, WIN_H))
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.PAUSED
            elif self.screen_id == Screen.PAUSED:
                self.screen_id = Screen.PLAYING
            else:
                self.screen_id = Screen.TITLE
            return

        if event.key == pygame.K_SPACE:
            if self.screen_id == Screen.TITLE:
                self.start_game()
            elif self.screen_id == Screen.PLAYING and self.balls:
                self._launch_ball(self.balls[0])
            elif self.screen_id == Screen.GAME_OVER:
                self.start_game()

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
    BrickBreakerGame().run()


if __name__ == "__main__":
    main()
