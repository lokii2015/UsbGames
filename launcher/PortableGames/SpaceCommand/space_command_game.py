#!/usr/bin/env python3
"""UsbGames Space Command — retro vertical space shooter."""

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

GAME_ID = "SpaceCommand"

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
PLAY_TOP = HUD_H + 8
PLAY_BOTTOM = WIN_H - 24

COL_BG = (10, 14, 22)
COL_BG2 = (14, 20, 32)
COL_TURQ = (64, 224, 208)
COL_TURQ_DIM = (32, 140, 128)
COL_GREEN = (57, 255, 120)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_RED = (255, 90, 90)
COL_ORANGE = (255, 160, 60)
COL_STAR = (80, 120, 140)

SAMPLE_RATE = 22050
PLAYER_SPEED = 280.0
BULLET_SPEED = 520.0
ENEMY_BULLET_SPEED = 220.0


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("spacecommand", "space-command", "space command"):
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
            self.shoot = _tone(720, 35, 0.2)
            self.enemy_shoot = _tone(180, 40, 0.15)
            self.explode = _tone(90, 120, 0.28)
            self.hit = _tone(140, 90, 0.3)
            self.power = _tone(880, 70, 0.25)
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


class PowerKind(Enum):
    DOUBLE = "double"
    RAPID = "rapid"
    SHIELD = "shield"
    SPREAD = "spread"


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    friendly: bool
    damage: int = 1

    def rect(self) -> pygame.Rect:
        w, h = (4, 10) if self.friendly else (4, 8)
        return pygame.Rect(int(self.x - w // 2), int(self.y - h // 2), w, h)


@dataclass
class Enemy:
    x: float
    y: float
    vx: float
    vy: float
    hp: int
    etype: str
    shoot_cd: float = 0.0
    wobble: float = 0.0

    def rect(self) -> pygame.Rect:
        if self.etype == "heavy":
            return pygame.Rect(int(self.x - 18), int(self.y - 14), 36, 28)
        return pygame.Rect(int(self.x - 14), int(self.y - 12), 28, 24)


@dataclass
class PowerUp:
    x: float
    y: float
    vy: float
    kind: PowerKind

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 10), int(self.y - 10), 20, 20)


class Screen(Enum):
    TITLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class SpaceCommandGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Space Command — UsbGames")
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
        self.wave = 1
        self.lives = 3
        self.player_x = WIN_W / 2
        self.player_y = PLAY_BOTTOM - 36
        self.fire_cd = 0.0
        self.invuln = 0.0
        self.shield = False
        self.double_damage = False
        self.rapid_fire = False
        self.spread_shot = False
        self.power_timer = 0.0
        self.bullets: List[Bullet] = []
        self.enemies: List[Enemy] = []
        self.powerups: List[PowerUp] = []
        self._buttons: List[Tuple[pygame.Rect, str, str]] = []
        self._hover: Optional[str] = None
        self._wave_timer = 0.0
        self._spawn_queue = 0
        self._stars = [(random.randint(0, WIN_W), random.randint(PLAY_TOP, WIN_H)) for _ in range(50)]
        self._keys = {
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_a: False,
            pygame.K_d: False,
            pygame.K_w: False,
            pygame.K_s: False,
            pygame.K_SPACE: False,
        }
        self._title_pulse = 0.0

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

    def _player_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.player_x - 16), int(self.player_y - 14), 32, 28)

    def start_game(self) -> None:
        self.score = 0
        self.wave = 1
        self.lives = 3
        self.player_x = WIN_W / 2
        self.player_y = PLAY_BOTTOM - 36
        self._clear_powers()
        self.bullets.clear()
        self.enemies.clear()
        self.powerups.clear()
        self._spawn_wave()
        self.screen_id = Screen.PLAYING
        self.invuln = 1.5

    def _clear_powers(self) -> None:
        self.shield = False
        self.double_damage = False
        self.rapid_fire = False
        self.spread_shot = False
        self.power_timer = 0.0

    def _spawn_wave(self) -> None:
        self.enemies.clear()
        count = 4 + self.wave * 2
        cols = min(6, 2 + self.wave // 2)
        rows = max(1, count // cols)
        margin = 40
        step_x = (WIN_W - margin * 2) / max(cols - 1, 1)
        idx = 0
        for row in range(rows):
            for col in range(cols):
                if idx >= count:
                    break
                x = margin + col * step_x
                y = PLAY_TOP + 30 + row * 36
                etype = "heavy" if self.wave >= 3 and idx % 5 == 0 else "scout"
                hp = 3 if etype == "heavy" else 1 + self.wave // 4
                self.enemies.append(
                    Enemy(
                        x=x,
                        y=y,
                        vx=random.choice([-1, 1]) * (40 + self.wave * 8),
                        vy=30 + self.wave * 6,
                        hp=hp,
                        etype=etype,
                        shoot_cd=random.uniform(0.5, 2.0),
                        wobble=random.random() * math.pi * 2,
                    )
                )
                idx += 1
        self._spawn_queue = 0

    def _fire_player(self) -> None:
        rate = 0.12 if self.rapid_fire else 0.22
        if self.fire_cd > 0:
            return
        self.fire_cd = rate
        dmg = 2 if self.double_damage else 1
        self.audio.play(self.audio.shoot)
        if self.spread_shot:
            for ang in (-0.18, 0.0, 0.18):
                self.bullets.append(
                    Bullet(
                        self.player_x,
                        self.player_y - 16,
                        math.sin(ang) * 80,
                        -BULLET_SPEED,
                        True,
                        dmg,
                    )
                )
        else:
            self.bullets.append(
                Bullet(self.player_x, self.player_y - 16, 0, -BULLET_SPEED, True, dmg)
            )

    def _spawn_powerup(self, x: float, y: float) -> None:
        if random.random() > 0.28:
            return
        kind = random.choice(list(PowerKind))
        self.powerups.append(PowerUp(x, y, 90.0, kind))

    def _apply_power(self, kind: PowerKind) -> None:
        self.audio.play(self.audio.power)
        self.power_timer = 10.0
        self._clear_powers()
        if kind == PowerKind.DOUBLE:
            self.double_damage = True
        elif kind == PowerKind.RAPID:
            self.rapid_fire = True
        elif kind == PowerKind.SHIELD:
            self.shield = True
            self.power_timer = 0.0
        elif kind == PowerKind.SPREAD:
            self.spread_shot = True

    def _hurt_player(self) -> None:
        if self.invuln > 0:
            return
        if self.shield:
            self.shield = False
            self.audio.play(self.audio.hit)
            self.invuln = 1.2
            return
        self.audio.play(self.audio.hit)
        self.lives -= 1
        self.invuln = 2.0
        self._clear_powers()
        if self.lives <= 0:
            self._game_over()

    def _game_over(self) -> None:
        if self.score > self.highscore:
            self.highscore = self.score
        self.score_history.insert(0, self.score)
        self.score_history = sorted(set(self.score_history), reverse=True)[:10]
        save_highscore(self.highscore, self.score_history)
        self.screen_id = Screen.GAME_OVER

    def _kill_enemy(self, enemy: Enemy) -> None:
        pts = 100 if enemy.etype == "heavy" else 50
        if self.double_damage:
            pts *= 2
        self.score += pts
        self.audio.play(self.audio.explode)
        self._spawn_powerup(enemy.x, enemy.y)
        if enemy in self.enemies:
            self.enemies.remove(enemy)

    def update(self, dt: float) -> None:
        self._title_pulse += dt
        if self.screen_id != Screen.PLAYING:
            return

        if self.invuln > 0:
            self.invuln -= dt
        if self.fire_cd > 0:
            self.fire_cd -= dt
        if self.power_timer > 0:
            self.power_timer -= dt
            if self.power_timer <= 0 and not self.shield:
                self._clear_powers()

        spd = PLAYER_SPEED
        if self._keys[pygame.K_LEFT] or self._keys[pygame.K_a]:
            self.player_x -= spd * dt
        if self._keys[pygame.K_RIGHT] or self._keys[pygame.K_d]:
            self.player_x += spd * dt
        if self._keys[pygame.K_UP] or self._keys[pygame.K_w]:
            self.player_y -= spd * dt
        if self._keys[pygame.K_DOWN] or self._keys[pygame.K_s]:
            self.player_y += spd * dt
        self.player_x = max(24, min(WIN_W - 24, self.player_x))
        self.player_y = max(PLAY_TOP + 40, min(PLAY_BOTTOM - 20, self.player_y))

        if self._keys[pygame.K_SPACE]:
            self._fire_player()

        pr = self._player_rect()
        for i, (sx, sy) in enumerate(self._stars):
            self._stars[i] = (sx, (sy + 40 * dt) % (WIN_H - PLAY_TOP) + PLAY_TOP)

        for enemy in list(self.enemies):
            enemy.wobble += dt * 3
            enemy.x += enemy.vx * dt + math.sin(enemy.wobble) * 30 * dt
            enemy.y += enemy.vy * dt
            if enemy.x < 30 or enemy.x > WIN_W - 30:
                enemy.vx *= -1
            enemy.shoot_cd -= dt
            if enemy.shoot_cd <= 0 and enemy.y < self.player_y - 20:
                enemy.shoot_cd = random.uniform(1.2, 2.8) - self.wave * 0.05
                enemy.shoot_cd = max(0.6, enemy.shoot_cd)
                self.bullets.append(
                    Bullet(enemy.x, enemy.y + 12, 0, ENEMY_BULLET_SPEED, False, 1)
                )
                self.audio.play(self.audio.enemy_shoot)
            if enemy.y > PLAY_BOTTOM + 40:
                self.enemies.remove(enemy)

        for b in list(self.bullets):
            b.x += b.vx * dt
            b.y += b.vy * dt
            br = b.rect()
            if b.y < PLAY_TOP - 20 or b.y > WIN_H + 20 or b.x < -20 or b.x > WIN_W + 20:
                self.bullets.remove(b)
                continue
            if b.friendly:
                for enemy in list(self.enemies):
                    if br.colliderect(enemy.rect()):
                        enemy.hp -= b.damage
                        if b in self.bullets:
                            self.bullets.remove(b)
                        if enemy.hp <= 0:
                            self._kill_enemy(enemy)
                        else:
                            self.audio.play(self.audio.hit)
                        break
            elif br.colliderect(pr):
                self.bullets.remove(b)
                self._hurt_player()

        for pu in list(self.powerups):
            pu.y += pu.vy * dt
            if pu.rect().colliderect(pr):
                self._apply_power(pu.kind)
                self.powerups.remove(pu)
            elif pu.y > WIN_H:
                self.powerups.remove(pu)

        if not self.enemies and self.screen_id == Screen.PLAYING:
            self._wave_timer += dt
            if self._wave_timer > 1.2:
                self.wave += 1
                self._wave_timer = 0.0
                self.score += 200
                self._spawn_wave()
                self.invuln = 1.0

    def _draw_bg(self) -> None:
        for y in range(PLAY_TOP, WIN_H, 40):
            shade = COL_BG if ((y - PLAY_TOP) // 40) % 2 == 0 else COL_BG2
            pygame.draw.rect(self.screen, shade, (0, y, WIN_W, 40))
        for sx, sy in self._stars:
            pygame.draw.rect(self.screen, COL_STAR, (int(sx), int(sy), 2, 2))

    def _draw_ship(self) -> None:
        x, y = int(self.player_x), int(self.player_y)
        if self.invuln > 0 and int(self.invuln * 8) % 2 == 0:
            return
        pygame.draw.polygon(
            self.screen,
            COL_TURQ,
            [(x, y - 16), (x - 14, y + 12), (x + 14, y + 12)],
        )
        pygame.draw.polygon(self.screen, COL_GREEN, [(x, y - 10), (x - 6, y + 4), (x + 6, y + 4)])
        if self.shield:
            pygame.draw.circle(self.screen, COL_TURQ, (x, y), 22, 2)

    def _draw_enemy(self, e: Enemy) -> None:
        r = e.rect()
        col = COL_ORANGE if e.etype == "heavy" else COL_RED
        pygame.draw.rect(self.screen, col, r)
        pygame.draw.rect(self.screen, COL_TURQ_DIM, r, 2)
        pygame.draw.rect(self.screen, (255, 255, 255), (r.centerx - 2, r.centery - 2, 4, 4))

    def _draw_bullet(self, b: Bullet) -> None:
        r = b.rect()
        col = COL_GREEN if b.friendly else COL_RED
        if b.friendly and self.double_damage:
            col = COL_TURQ
        pygame.draw.rect(self.screen, col, r)

    def _draw_powerup(self, pu: PowerUp) -> None:
        colors = {
            PowerKind.DOUBLE: COL_TURQ,
            PowerKind.RAPID: COL_GREEN,
            PowerKind.SHIELD: (120, 180, 255),
            PowerKind.SPREAD: COL_ORANGE,
        }
        labels = {
            PowerKind.DOUBLE: "2X",
            PowerKind.RAPID: "R",
            PowerKind.SHIELD: "S",
            PowerKind.SPREAD: "*",
        }
        pygame.draw.rect(self.screen, colors[pu.kind], pu.rect(), border_radius=4)
        self._pixel_text(labels[pu.kind], int(pu.x), int(pu.y) - 6, self.font_xs, COL_BG, center=True)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (6, 8, 14), (0, 0, WIN_W, HUD_H))
        self._pixel_text(f"SCORE {self.score}", 12, 8, self.font_sm, COL_TEXT)
        self._pixel_text(f"WAVE {self.wave}", WIN_W // 2, 8, self.font_sm, COL_TURQ, center=True)
        hearts = "♥" * self.lives + "♡" * max(0, 3 - self.lives)
        surf = self.font_sm.render(hearts, True, COL_RED)
        self.screen.blit(surf, (WIN_W - surf.get_width() - 12, 8))
        if self.power_timer > 0 or self.shield:
            pwr = []
            if self.double_damage:
                pwr.append("2X")
            if self.rapid_fire:
                pwr.append("RAPID")
            if self.spread_shot:
                pwr.append("SPREAD")
            if self.shield:
                pwr.append("SHIELD")
            self._pixel_text(" ".join(pwr), WIN_W // 2, 26, self.font_xs, COL_GREEN, center=True)

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
        elif self.screen_id in (Screen.PLAYING, Screen.PAUSED):
            self._draw_play()
            if self.screen_id == Screen.PAUSED:
                self._draw_pause()
        elif self.screen_id == Screen.GAME_OVER:
            self._draw_play(frozen=True)
            self._draw_game_over()
        _present_display(self._display, self.screen)

    def _draw_title(self) -> None:
        self._draw_bg()
        pygame.draw.rect(self.screen, COL_TURQ, (24, 56, WIN_W - 48, WIN_H - 100), 2)
        self._pixel_text("SPACE COMMAND", WIN_W // 2, 100, self.font_lg, COL_TURQ, center=True)
        self._pixel_text("UsbGames", WIN_W // 2, 145, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"HIGH SCORE {self.highscore}", WIN_W // 2, 190, self.font_md, COL_GREEN, center=True)
        cx, cy = WIN_W // 2, 290
        pygame.draw.polygon(self.screen, COL_TURQ, [(cx, cy - 20), (cx - 16, cy + 14), (cx + 16, cy + 14)])
        for ex in (-50, 50):
            pygame.draw.rect(self.screen, COL_RED, (cx + ex - 12, cy - 30, 24, 18))
        self._make_btn(360, "PLAY", "play")
        self._draw_buttons()
        self._pixel_text("WASD / ARROWS — MOVE", WIN_W // 2, WIN_H - 72, self.font_xs, COL_DIM, center=True)
        self._pixel_text("SPACE — FIRE", WIN_W // 2, WIN_H - 52, self.font_xs, COL_DIM, center=True)

    def _draw_play(self, frozen: bool = False) -> None:
        self._draw_bg()
        for e in self.enemies:
            self._draw_enemy(e)
        for pu in self.powerups:
            self._draw_powerup(pu)
        for b in self.bullets:
            self._draw_bullet(b)
        self._draw_ship()
        self._draw_hud()
        if not self.enemies and not frozen and self.screen_id == Screen.PLAYING:
            self._pixel_text("WAVE CLEAR!", WIN_W // 2, WIN_H // 2, self.font_md, COL_GREEN, center=True)

    def _draw_pause(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("PAUSED", WIN_W // 2, WIN_H // 2 - 20, self.font_lg, COL_TURQ, center=True)

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))
        self._pixel_text("GAME OVER", WIN_W // 2, 140, self.font_lg, COL_TURQ, center=True)
        self._pixel_text(f"SCORE {self.score}", WIN_W // 2, 195, self.font_md, COL_TEXT, center=True)
        self._pixel_text(f"WAVE {self.wave}", WIN_W // 2, 235, self.font_sm, COL_DIM, center=True)
        self._pixel_text(f"BEST {self.highscore}", WIN_W // 2, 270, self.font_sm, COL_GREEN, center=True)
        if self.score >= self.highscore and self.score > 0:
            self._pixel_text("NEW HIGH SCORE!", WIN_W // 2, 305, self.font_sm, COL_TURQ, center=True)
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
            elif self.screen_id == Screen.GAME_OVER:
                self.start_game()
            return

        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_F11:
            self._fullscreen = not self._fullscreen
            self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self._fullscreen else pygame.display.set_mode((WIN_W, WIN_H))
            return
        if event.key == pygame.K_ESCAPE:
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.PAUSED
            elif self.screen_id == Screen.PAUSED:
                self.screen_id = Screen.PLAYING
            else:
                self.screen_id = Screen.TITLE
            return
        if event.key == pygame.K_SPACE and self.screen_id == Screen.TITLE:
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
    SpaceCommandGame().run()


if __name__ == "__main__":
    main()
