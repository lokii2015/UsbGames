#!/usr/bin/env python3
"""UsbGames Pixel Flap — retro endless flap arcade."""

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

GAME_ID = "PixelFlapTurbo"
CHAR_ORDER = ("drone", "bird", "rocket")
CHAR_LABELS = {"drone": "DRONE", "bird": "BIRD", "rocket": "ROCKET"}


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("pixelflap", "pixel-flap", "pixel flap", "pixelflapturbo"):
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


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

WIN_W, WIN_H = 400, 600
FPS_CAP = 60
GROUND_H = 56
HUD_H = 44

COL_BG = (10, 14, 22)
COL_BG2 = (14, 20, 32)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 140, 128)
COL_GREEN = (57, 255, 120)
COL_PIPE = (32, 48, 58)
COL_PIPE_EDGE = (64, 224, 208)
COL_GROUND = (22, 30, 38)
COL_GROUND_TOP = (64, 224, 208)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_STAR = (80, 120, 140)

GRAVITY = 1450.0
FLAP_VEL = -340.0
PIPE_W = 58
GAP_MIN = 118
GAP_MAX = 158
PIPE_SPACING = 200
BASE_SPEED = 155.0
MAX_SPEED = 240.0

SAMPLE_RATE = 22050


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
            self.flap = _tone(520, 55, 0.28)
            self.score = _tone(880, 70, 0.25)
            self.hit = _tone(120, 180, 0.35)
            self.ui = _tone(660, 40, 0.2)
        except pygame.error:
            self.enabled = False

    def play(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and self.sfx_on and snd:
            snd.play()


# ---------------------------------------------------------------------------
# High score / profile
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


@dataclass
class Pipe:
    x: float
    gap_y: int
    gap_h: int
    scored: bool = False
    moving: bool = False
    move_phase: float = 0.0

    def rects(self) -> List[pygame.Rect]:
        top_h = self.gap_y
        bot_y = self.gap_y + self.gap_h
        play_h = WIN_H - GROUND_H
        return [
            pygame.Rect(int(self.x), 0, PIPE_W, top_h),
            pygame.Rect(int(self.x), bot_y, PIPE_W, play_h - bot_y),
        ]


@dataclass
class Spike:
    x: float
    y: int


@dataclass
class PowerUp:
    x: float
    y: int
    kind: str
    taken: bool = False


class Screen(Enum):
    TITLE = auto()
    PLAYING = auto()
    GAME_OVER = auto()


class PixelFlapGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Pixel Flap Turbo — UsbGames")
        self.screen = pygame.display.set_mode(
            (WIN_W, WIN_H), pygame.FULLSCREEN if self.fullscreen else 0
        )
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("courier", 32, bold=True)
        self.font_md = pygame.font.SysFont("courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("courier", 16)
        self.font_xs = pygame.font.SysFont("courier", 14)

        self.audio = Audio()
        self.settings = load_json(SETTINGS_PATH, {"sfx": True, "character": "drone"})
        self.audio.sfx_on = self.settings.get("sfx", True)

        self.highscore, self.score_history = load_highscore()
        self.screen_id = Screen.TITLE
        self.score = 0
        self.bird_y = WIN_H * 0.42
        self.bird_vy = 0.0
        self.bird_x = WIN_W * 0.28
        self.bird_rot = 0.0
        self.pipes: List[Pipe] = []
        self.pipe_speed = BASE_SPEED
        self.elapsed = 0.0
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._stars = [(random.randint(0, WIN_W), random.randint(0, WIN_H - GROUND_H)) for _ in range(40)]
        self._title_pulse = 0.0
        self._ready = True
        self.level = 1
        self.spikes: List[Spike] = []
        self.powerups: List[PowerUp] = []
        self.shield_t = 0.0
        self.slow_t = 0.0
        self.double_t = 0.0
        self.fullscreen = True
        self._spawn_cd = 0.0

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

    def _reset_run(self) -> None:
        self.score = 0
        self.level = 1
        self.bird_y = WIN_H * 0.42
        self.bird_vy = 0.0
        self.bird_rot = 0.0
        self.pipes.clear()
        self.spikes.clear()
        self.powerups.clear()
        self.pipe_speed = BASE_SPEED
        self.elapsed = 0.0
        self.shield_t = self.slow_t = self.double_t = 0.0
        self._ready = True
        gap = random.randint(GAP_MIN, GAP_MAX)
        gy = random.randint(80, WIN_H - GROUND_H - gap - 80)
        self.pipes.append(Pipe(x=WIN_W + 40, gap_y=gy, gap_h=gap))
        self._spawn_pipe(WIN_W + 40 + PIPE_SPACING)

    def _spawn_pipe(self, x: float) -> None:
        gap = max(90, GAP_MAX - self.level * 4)
        gap = random.randint(max(90, gap - 20), gap)
        gy = random.randint(70, WIN_H - GROUND_H - gap - 70)
        moving = self.level >= 2 and random.random() < 0.35
        self.pipes.append(Pipe(x=x, gap_y=gy, gap_h=gap, moving=moving, move_phase=random.random() * 6))
        if self.level >= 3 and random.random() < 0.45:
            sy = gy + gap // 2 - 20
            self.spikes.append(Spike(x=x + PIPE_W // 2, y=sy))
        if random.random() < 0.22:
            kinds = ["shield", "slow", "double"]
            self.powerups.append(
                PowerUp(x=x + 20, y=gy + gap // 2, kind=random.choice(kinds))
            )

    def _bird_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.bird_x) - 14, int(self.bird_y) - 12, 28, 24)

    def flap(self) -> None:
        if self.screen_id == Screen.TITLE:
            self.start_game()
            return
        if self.screen_id != Screen.PLAYING:
            return
        if self._ready:
            self._ready = False
            self.bird_vy = FLAP_VEL * 0.6
        else:
            self.bird_vy = FLAP_VEL
        self.audio.play(self.audio.flap)

    def start_game(self) -> None:
        self._reset_run()
        self.screen_id = Screen.PLAYING

    def _game_over(self) -> None:
        self.audio.play(self.audio.hit)
        if self.score > self.highscore:
            self.highscore = self.score
        self.score_history.insert(0, self.score)
        self.score_history = sorted(set(self.score_history), reverse=True)[:10]
        save_highscore(self.highscore, self.score_history)
        self.screen_id = Screen.GAME_OVER

    def update(self, dt: float) -> None:
        self._title_pulse += dt
        if self.screen_id != Screen.PLAYING:
            return

        if self._ready:
            self.bird_y = WIN_H * 0.42 + math.sin(self._title_pulse * 4) * 8
            return

        self.elapsed += dt
        if self.shield_t > 0:
            self.shield_t -= dt
        if self.slow_t > 0:
            self.slow_t -= dt
        if self.double_t > 0:
            self.double_t -= dt
        spd_mul = 0.72 if self.slow_t > 0 else 1.0
        self.pipe_speed = min(MAX_SPEED, BASE_SPEED + self.elapsed * 2.8 + self.level * 8) * spd_mul

        grav = GRAVITY * (0.85 if self.slow_t > 0 else 1.0)
        self.bird_vy += grav * dt
        self.bird_y += self.bird_vy * dt
        self.bird_rot = max(-25, min(70, self.bird_vy * 0.12))

        play_bottom = WIN_H - GROUND_H
        if self.bird_y >= play_bottom - 16:
            self._game_over()
            return
        if self.bird_y < 0:
            self._game_over()
            return

        bird_r = self._bird_rect()
        for pipe in self.pipes:
            pipe.x -= self.pipe_speed * dt
            if pipe.moving:
                pipe.gap_y += int(math.sin(self.elapsed * 3 + pipe.move_phase) * 40 * dt)
                pipe.gap_y = max(50, min(WIN_H - GROUND_H - pipe.gap_h - 50, pipe.gap_y))
            for pr in pipe.rects():
                if bird_r.colliderect(pr) and self.shield_t <= 0:
                    self._game_over()
                    return
            if not pipe.scored and pipe.x + PIPE_W < self.bird_x:
                pipe.scored = True
                pts = 2 if self.double_t > 0 else 1
                self.score += pts
                self.audio.play(self.audio.score)
                if self.score // 5 + 1 > self.level:
                    self.level = self.score // 5 + 1

        for sp in self.spikes:
            sp.x -= self.pipe_speed * dt
            sr = pygame.Rect(int(sp.x), sp.y, 20, 36)
            if bird_r.colliderect(sr) and self.shield_t <= 0:
                self._game_over()
                return
        self.spikes = [s for s in self.spikes if s.x > -30]

        for pu in self.powerups:
            if pu.taken:
                continue
            pu.x -= self.pipe_speed * dt
            pr = pygame.Rect(int(pu.x), pu.y, 18, 18)
            if bird_r.colliderect(pr):
                pu.taken = True
                if pu.kind == "shield":
                    self.shield_t = 6.0
                elif pu.kind == "slow":
                    self.slow_t = 4.0
                else:
                    self.double_t = 8.0
                self.audio.play(self.audio.score)
        self.powerups = [p for p in self.powerups if not p.taken and p.x > -20]

        while self.pipes and self.pipes[0].x < -PIPE_W - 10:
            self.pipes.pop(0)
        if self.pipes and self.pipes[-1].x < WIN_W - PIPE_SPACING:
            self._spawn_pipe(self.pipes[-1].x + PIPE_SPACING)

        for i, (sx, sy) in enumerate(self._stars):
            self._stars[i] = ((sx - 20 * dt) % WIN_W, sy)

    def _draw_bird(self) -> None:
        surf = pygame.Surface((32, 28), pygame.SRCALPHA)
        ch = self.settings.get("character", "drone")
        if ch == "bird":
            pygame.draw.ellipse(surf, COL_GREEN, (6, 8, 20, 16))
            pygame.draw.rect(surf, COL_TURQ, (18, 10, 10, 8))
        elif ch == "rocket":
            pygame.draw.rect(surf, (200, 80, 255), (10, 6, 12, 18))
            pygame.draw.rect(surf, COL_TURQ, (8, 20, 16, 6))
        else:
            pygame.draw.rect(surf, COL_TURQ, (8, 10, 16, 12))
            pygame.draw.rect(surf, COL_GREEN, (20, 12, 8, 6))
        pygame.draw.rect(surf, COL_PIPE_EDGE, (4, 14, 6, 4))
        pygame.draw.rect(surf, (255, 255, 255), (22, 13, 3, 3))
        pygame.draw.rect(surf, COL_TURQ_DIM, (10, 8, 4, 3))
        rotated = pygame.transform.rotate(surf, -self.bird_rot)
        rect = rotated.get_rect(center=(int(self.bird_x), int(self.bird_y)))
        self.screen.blit(rotated, rect)

    def _draw_pipe(self, pipe: Pipe) -> None:
        for i, r in enumerate(pipe.rects()):
            pygame.draw.rect(self.screen, COL_PIPE, r)
            pygame.draw.rect(self.screen, COL_PIPE_EDGE, r, 2)
            # pixel cap
            cap = pygame.Rect(r.x - 4, r.bottom - 18 if i == 0 else r.top, r.width + 8, 18)
            if i == 0:
                cap.top = r.bottom - 18
            pygame.draw.rect(self.screen, COL_PIPE_EDGE, cap)
            pygame.draw.rect(self.screen, COL_TURQ, cap, 1)

    def _draw_ground(self) -> None:
        gy = WIN_H - GROUND_H
        pygame.draw.rect(self.screen, COL_GROUND, (0, gy, WIN_W, GROUND_H))
        pygame.draw.line(self.screen, COL_GROUND_TOP, (0, gy), (WIN_W, gy), 3)
        for x in range(0, WIN_W, 24):
            off = int((self.elapsed * 80 + x) % 24)
            pygame.draw.rect(self.screen, COL_TURQ_DIM, (x - off, gy + 12, 12, 4))

    def _draw_bg(self) -> None:
        for y in range(0, WIN_H - GROUND_H, 40):
            shade = COL_BG if (y // 40) % 2 == 0 else COL_BG2
            pygame.draw.rect(self.screen, shade, (0, y, WIN_W, 40))
        for sx, sy in self._stars:
            pygame.draw.rect(self.screen, COL_STAR, (int(sx), int(sy), 2, 2))

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
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_play(frozen=True)
            self._draw_game_over()

        pygame.display.flip()

    def _draw_title(self) -> None:
        self._draw_bg()
        pygame.draw.rect(self.screen, COL_TURQ, (24, 48, WIN_W - 48, WIN_H - 120), 2)
        self._pixel_text("PIXEL FLAP TURBO", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames", WIN_W // 2, 145, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"HIGH SCORE {self.highscore}", WIN_W // 2, 185, self.font_md, COL_GREEN, center=True)
        self._draw_bird_at(WIN_W // 2, 260)
        self._make_btn(340, "PLAY", "play")
        self._draw_buttons()
        self._pixel_text("SPACE / CLICK TO FLAP", WIN_W // 2, WIN_H - 70, self.font_xs, COL_DIM, center=True)

    def _draw_bird_at(self, x: float, y: float) -> None:
        old_x, old_y, old_rot = self.bird_x, self.bird_y, self.bird_rot
        self.bird_x, self.bird_y, self.bird_rot = x, y, -10
        self._draw_bird()
        self.bird_x, self.bird_y, self.bird_rot = old_x, old_y, old_rot

    def _draw_play(self, frozen: bool = False) -> None:
        self._draw_bg()
        for pipe in self.pipes:
            self._draw_pipe(pipe)
        for sp in self.spikes:
            pygame.draw.polygon(
                self.screen,
                (255, 60, 80),
                [(int(sp.x), sp.y + 36), (int(sp.x) + 10, sp.y), (int(sp.x) + 20, sp.y + 36)],
            )
        for pu in self.powerups:
            if pu.taken:
                continue
            col = (80, 200, 255) if pu.kind == "shield" else (255, 220, 80) if pu.kind == "double" else (180, 120, 255)
            pygame.draw.rect(self.screen, col, (int(pu.x), pu.y, 16, 16))
        self._draw_ground()
        self._draw_bird()

        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        self._pixel_text(f"{self.score}", WIN_W // 2, 6, self.font_lg, COL_TEXT, center=True)
        self._pixel_text(f"LV {self.level}", 12, 8, self.font_xs, COL_TURQ)
        if self.shield_t > 0:
            self._pixel_text("SHIELD", WIN_W - 50, 8, self.font_xs, COL_GREEN)
        if self.double_t > 0:
            self._pixel_text("x2", WIN_W - 50, 24, self.font_xs, COL_TURQ)
        if self._ready and not frozen:
            self._pixel_text("GET READY", WIN_W // 2, WIN_H // 2 - 40, self.font_md, COL_TURQ, center=True)
            self._pixel_text("SPACE / CLICK", WIN_W // 2, WIN_H // 2, self.font_xs, COL_DIM, center=True)

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("GAME OVER", WIN_W // 2, 140, self.font_lg, COL_TURQ, center=True)
        self._pixel_text(f"SCORE {self.score}", WIN_W // 2, 195, self.font_md, COL_TEXT, center=True)
        self._pixel_text(f"BEST {self.highscore}", WIN_W // 2, 235, self.font_sm, COL_GREEN, center=True)
        if self.score >= self.highscore and self.score > 0:
            self._pixel_text("NEW HIGH SCORE!", WIN_W // 2, 270, self.font_sm, COL_TURQ, center=True)
        self._make_btn(340, "RETRY", "retry")
        self._make_btn(395, "MENU", "title")
        self._draw_buttons()

    def _hit_btn(self, pos: Tuple[int, int]) -> Optional[str]:
        for rect, _, action in self._buttons:
            if rect.collidepoint(pos):
                return action
        return None

    def _do_action(self, action: str) -> None:
        self.audio.play(self.audio.ui)
        if action == "play" or action == "retry":
            self.start_game()
        elif action == "title":
            self.screen_id = Screen.TITLE

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._hit_btn(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            act = self._hit_btn(event.pos)
            if act:
                self._do_action(act)
                return
            if self.screen_id in (Screen.PLAYING, Screen.TITLE):
                self.flap()
            elif self.screen_id == Screen.GAME_OVER:
                self.start_game()
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            self.screen = pygame.display.set_mode(
                (WIN_W, WIN_H), pygame.FULLSCREEN if self.fullscreen else 0
            )
            return
        if event.key == pygame.K_c:
            cur = self.settings.get("character", "drone")
            self.settings["character"] = CHAR_ORDER[(CHAR_ORDER.index(cur) + 1) % len(CHAR_ORDER)] if cur in CHAR_ORDER else "drone"
            save_json(SETTINGS_PATH, self.settings)
            return
        if event.key == pygame.K_SPACE:
            if self.screen_id == Screen.GAME_OVER:
                self.start_game()
            else:
                self.flap()
        if event.key == pygame.K_ESCAPE and self.screen_id == Screen.PLAYING:
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
    PixelFlapGame().run()


if __name__ == "__main__":
    main()
