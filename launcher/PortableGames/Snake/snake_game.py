#!/usr/bin/env python3
"""UsbGames Snake — retro pixel-art arcade Snake."""

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
# Paths (works frozen with PyInstaller or as script)
# ---------------------------------------------------------------------------

def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


ASSETS = os.path.join(app_dir(), "assets")
HIGHSCORE_PATH = os.path.join(app_dir(), "highscore.json")
SETTINGS_PATH = os.path.join(app_dir(), "settings.json")

# map_id -> (grid_w, grid_h, cell_px)
MAP_PRESETS: dict[str, Tuple[int, int, int]] = {
    "small": (28, 20, 20),
    "medium": (40, 28, 18),
    "large": (52, 36, 16),
}
MAP_ORDER = ("small", "medium", "large")
MAP_LABELS = {"small": "SMALL", "medium": "MEDIUM", "large": "LARGE"}

HUD_H = 48
FPS_CAP = 60

COL_BG = (12, 14, 18)
COL_GRID = (22, 26, 34)
COL_SNAKE = (57, 255, 20)
COL_SNAKE_HEAD = (120, 255, 90)
COL_SNAKE_SHADOW = (20, 80, 12)
COL_APPLE = (255, 45, 45)
COL_APPLE_HI = (255, 120, 100)
COL_HUD = (180, 200, 180)
COL_ACCENT = (57, 255, 20)
COL_TEXT = (220, 230, 220)
COL_DIM = (100, 110, 100)
COL_BTN = (30, 36, 44)
COL_BTN_HOVER = (45, 55, 50)
COL_BTN_BORDER = (57, 255, 20)
COL_OVERLAY = (0, 0, 0, 160)

# ---------------------------------------------------------------------------
# Audio (procedural — no asset files required)
# ---------------------------------------------------------------------------

SAMPLE_RATE = 22050


def _tone(freq: float, ms: int, volume: float = 0.35) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * ms / 1000)
    amp = int(32767 * volume)
    buf = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        # slight envelope
        env = min(1.0, i / (n * 0.05), (n - i) / (n * 0.12))
        sample = int(amp * env * math.sin(2 * math.pi * freq * t))
        buf.extend(struct.pack("<h", sample))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _noise_burst(ms: int, volume: float = 0.2) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * ms / 1000)
    amp = int(32767 * volume)
    buf = bytearray()
    for i in range(n):
        env = 1.0 - i / n
        sample = int(amp * env * (random.random() * 2 - 1))
        buf.extend(struct.pack("<h", sample))
    return pygame.mixer.Sound(buffer=bytes(buf))


class Audio:
    def __init__(self) -> None:
        self.enabled = True
        self.sfx_on = True
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.eat = _tone(520, 80, 0.3)
            self.death = _noise_burst(200, 0.35)
            self.ui = _tone(880, 40, 0.2)
        except pygame.error:
            self.enabled = False

    def play_sfx(self, snd: Optional[pygame.mixer.Sound]) -> None:
        if self.enabled and self.sfx_on and snd:
            snd.play()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Game logic
# ---------------------------------------------------------------------------

Vec = Tuple[int, int]
DIRS = {
  pygame.K_UP: (0, -1),
  pygame.K_DOWN: (0, 1),
  pygame.K_LEFT: (-1, 0),
  pygame.K_RIGHT: (1, 0),
  pygame.K_w: (0, -1),
  pygame.K_s: (0, 1),
  pygame.K_a: (-1, 0),
  pygame.K_d: (1, 0),
}


class Screen(Enum):
  TITLE = auto()
  PLAYING = auto()
  PAUSED = auto()
  GAME_OVER = auto()
  HIGHSCORES = auto()
  SETTINGS = auto()


class SnakeGame:
  def __init__(self) -> None:
    pygame.init()
    pygame.display.set_caption("Snake — UsbGames")
    self.clock = pygame.time.Clock()
    self.font_lg = pygame.font.SysFont("courier", 36, bold=True)
    self.font_md = pygame.font.SysFont("courier", 22, bold=True)
    self.font_sm = pygame.font.SysFont("courier", 16)
    self.font_xs = pygame.font.SysFont("courier", 14)

    self.audio = Audio()
    self.settings = load_json(
      SETTINGS_PATH,
      {"sfx": True, "show_grid": True, "map_size": "small"},
    )
    if self.settings.get("map_size") not in MAP_PRESETS:
      self.settings["map_size"] = "small"
    self.audio.sfx_on = self.settings.get("sfx", True)

    self.grid_w = 28
    self.grid_h = 20
    self.cell = 20
    self.win_w = 560
    self.win_h = 448
    self.screen: pygame.Surface
    self._apply_map_size(self.settings["map_size"], resize_now=True)

    hs = load_json(HIGHSCORE_PATH, {"highscore": 0, "scores": []})
    self.highscore: int = int(hs.get("highscore", 0))
    self.score_history: List[int] = list(hs.get("scores", []))[:10]

    self.screen_id = Screen.TITLE
    self.score = 0
    self.snake: List[Vec] = []
    self.direction: Vec = (1, 0)
    self.next_direction: Vec = (1, 0)
    self.apple: Vec = (5, 5)
    self.move_timer = 0.0
    self.move_interval = 0.14
    self.min_interval = 0.055
    self.apples_eaten = 0
    self._title_blink = 0.0
    self._buttons: List[Tuple[pygame.Rect, str, str]] = []
    self._hover: Optional[str] = None

    self._reset_snake()

  def _apply_map_size(self, map_id: str, resize_now: bool = False) -> None:
    if map_id not in MAP_PRESETS:
      map_id = "small"
    self.grid_w, self.grid_h, self.cell = MAP_PRESETS[map_id]
    self.win_w = self.grid_w * self.cell
    self.win_h = self.grid_h * self.cell + HUD_H
    self.settings["map_size"] = map_id
    if resize_now:
      self.screen = pygame.display.set_mode((self.win_w, self.win_h))

  def _reset_snake(self) -> None:
    cx, cy = self.grid_w // 2, self.grid_h // 2
    self.snake = [(cx - i, cy) for i in range(4)]
    self.direction = (1, 0)
    self.next_direction = (1, 0)
    self.score = 0
    self.apples_eaten = 0
    self.move_interval = 0.14
    self.move_timer = 0.0
    self._place_apple()

  def _place_apple(self) -> None:
    occupied = set(self.snake)
    while True:
      p = (random.randint(0, self.grid_w - 1), random.randint(0, self.grid_h - 1))
      if p not in occupied:
        self.apple = p
        return

  def _grid_rect(self, gx: int, gy: int) -> pygame.Rect:
    return pygame.Rect(gx * self.cell, gy * self.cell + HUD_H, self.cell, self.cell)

  def start_game(self) -> None:
    self._apply_map_size(self.settings.get("map_size", "small"), resize_now=True)
    self._reset_snake()
    self.screen_id = Screen.PLAYING

  def _update_highscore(self) -> None:
    if self.score > self.highscore:
      self.highscore = self.score
    self.score_history.insert(0, self.score)
    self.score_history = sorted(self.score_history, reverse=True)[:10]
    save_json(
      HIGHSCORE_PATH,
      {"highscore": self.highscore, "scores": self.score_history},
    )

  def _save_settings(self) -> None:
    save_json(SETTINGS_PATH, self.settings)

  # --- update ---

  def update(self, dt: float) -> None:
    self._title_blink += dt
    if self.screen_id == Screen.PLAYING:
      self._update_playing(dt)
    elif self.screen_id == Screen.PAUSED:
      pass

  def _update_playing(self, dt: float) -> None:
    # queue direction (no 180° turn)
    if self.next_direction != (-self.direction[0], -self.direction[1]):
      self.direction = self.next_direction

    self.move_timer += dt
    if self.move_timer < self.move_interval:
      return
    self.move_timer = 0.0

    hx, hy = self.snake[0]
    dx, dy = self.direction
    nx, ny = hx + dx, hy + dy

    # wall collision
    if nx < 0 or nx >= self.grid_w or ny < 0 or ny >= self.grid_h:
      self._game_over()
      return

    new_head = (nx, ny)

    # self collision (tail moves unless we grow)
    will_grow = new_head == self.apple
    body_check = self.snake if will_grow else self.snake[:-1]
    if new_head in body_check:
      self._game_over()
      return

    self.snake.insert(0, new_head)
    if will_grow:
      self.score += 10
      self.apples_eaten += 1
      self.move_interval = max(
        self.min_interval,
        self.move_interval - 0.004,
      )
      self.audio.play_sfx(self.audio.eat)
      self._place_apple()
    else:
      self.snake.pop()

  def _game_over(self) -> None:
    self.audio.play_sfx(self.audio.death)
    self._update_highscore()
    self.screen_id = Screen.GAME_OVER

  # --- draw helpers ---

  def _draw_pixel_text(
    self,
    text: str,
    x: int,
    y: int,
    font: pygame.font.Font,
    color: Tuple[int, int, int],
    center_x: bool = False,
  ) -> None:
    surf = font.render(text, True, color)
    # chunky pixel look: scale up then down
    big = pygame.transform.scale(surf, (surf.get_width() * 2, surf.get_height() * 2))
    pix = pygame.transform.scale(
      big,
      (surf.get_width(), surf.get_height()),
    )
    rx = x - pix.get_width() // 2 if center_x else x
    self.screen.blit(pix, (rx, y))

  def _draw_grid(self) -> None:
    play = pygame.Rect(0, HUD_H, self.win_w, self.grid_h * self.cell)
    pygame.draw.rect(self.screen, COL_BG, play)
    if not self.settings.get("show_grid", True):
      return
    for x in range(self.grid_w + 1):
      pygame.draw.line(
        self.screen,
        COL_GRID,
        (x * self.cell, HUD_H),
        (x * self.cell, HUD_H + self.grid_h * self.cell),
      )
    for y in range(self.grid_h + 1):
      pygame.draw.line(
        self.screen,
        COL_GRID,
        (0, HUD_H + y * self.cell),
        (self.win_w, HUD_H + y * self.cell),
      )

  def _draw_hud(self) -> None:
    pygame.draw.rect(self.screen, (8, 10, 12), (0, 0, self.win_w, HUD_H))
    pygame.draw.line(self.screen, COL_ACCENT, (0, HUD_H - 2), (self.win_w, HUD_H - 2), 2)
    self._draw_pixel_text(f"SCORE {self.score:04d}", 12, 10, self.font_md, COL_TEXT)
    self._draw_pixel_text(
      f"HI {self.highscore:04d}",
      self.win_w - 12,
      10,
      self.font_md,
      COL_ACCENT,
      center_x=True,
    )
    map_lbl = MAP_LABELS.get(self.settings.get("map_size", "small"), "SMALL")
    self._draw_pixel_text(map_lbl, self.win_w // 2, 28, self.font_xs, COL_DIM, center_x=True)
    if self.screen_id == Screen.PAUSED:
      self._draw_pixel_text("PAUSED", self.win_w // 2, 10, self.font_md, COL_DIM, center_x=True)

  def _draw_snake(self) -> None:
    for i, (gx, gy) in enumerate(self.snake):
      r = self._grid_rect(gx, gy)
      inner = r.inflate(-4, -4)
      if i == 0:
        pygame.draw.rect(self.screen, COL_SNAKE_HEAD, inner)
        # eyes
        ex = 4 if self.direction[0] >= 0 else inner.width - 8
        ey = inner.height // 2 - 3
        pygame.draw.rect(self.screen, COL_BG, (inner.x + ex, inner.y + ey, 3, 3))
        pygame.draw.rect(
          self.screen,
          COL_BG,
          (inner.x + ex, inner.y + ey + 6, 3, 3),
        )
      else:
        shade = max(20, COL_SNAKE[0] - i * 3)
        pygame.draw.rect(
          self.screen,
          (shade, COL_SNAKE[1] - min(i * 2, 80), COL_SNAKE[2] // 2),
          inner,
        )
      pygame.draw.rect(self.screen, COL_SNAKE_SHADOW, r, 1)

  def _draw_apple(self) -> None:
    r = self._grid_rect(*self.apple)
    cx, cy = r.centerx, r.centery
    pygame.draw.circle(self.screen, COL_APPLE, (cx, cy), self.cell // 2 - 2)
    pygame.draw.circle(self.screen, COL_APPLE_HI, (cx - 3, cy - 3), 3)
    # stem
    pygame.draw.rect(self.screen, (40, 120, 40), (cx - 1, cy - self.cell // 2, 2, 5))

  def _make_button(
    self,
    y: int,
    label: str,
    action: str,
    w: int = 200,
    h: int = 40,
  ) -> pygame.Rect:
    rect = pygame.Rect(self.win_w // 2 - w // 2, y, w, h)
    self._buttons.append((rect, label, action))
    return rect

  def _draw_buttons(self) -> None:
    for rect, label, action in self._buttons:
      hover = self._hover == action
      bg = COL_BTN_HOVER if hover else COL_BTN
      pygame.draw.rect(self.screen, bg, rect, border_radius=0)
      border = COL_BTN_BORDER if hover else COL_DIM
      pygame.draw.rect(self.screen, border, rect, 2)
      self._draw_pixel_text(label, rect.centerx, rect.centery - 8, self.font_md, COL_TEXT, center_x=True)

  def _draw_overlay(self) -> None:
    overlay = pygame.Surface((self.win_w, self.win_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    self.screen.blit(overlay, (0, 0))

  # --- screens ---

  def draw(self) -> None:
    self.screen.fill(COL_BG)
    self._buttons.clear()

    if self.screen_id == Screen.TITLE:
      self._draw_title()
    elif self.screen_id in (Screen.PLAYING, Screen.PAUSED):
      self._draw_play()
    elif self.screen_id == Screen.GAME_OVER:
      self._draw_play()
      self._draw_game_over()
    elif self.screen_id == Screen.HIGHSCORES:
      self._draw_highscores()
    elif self.screen_id == Screen.SETTINGS:
      self._draw_settings()

    pygame.display.flip()

  def _draw_title(self) -> None:
    # decorative border
    pygame.draw.rect(self.screen, COL_ACCENT, (20, 30, self.win_w - 40, self.win_h - 60), 2)
    self._draw_pixel_text("SNAKE", self.win_w // 2, 70, self.font_lg, COL_ACCENT, center_x=True)
    self._draw_pixel_text("UsbGames", self.win_w // 2, 115, self.font_sm, COL_DIM, center_x=True)

    if int(self._title_blink * 2) % 2 == 0:
      self._draw_pixel_text(
        "PRESS START",
        self.win_w // 2,
        155,
        self.font_sm,
        COL_TEXT,
        center_x=True,
      )

    cy = self.win_h // 2
    self._make_button(cy - 30, "PLAY", "play")
    self._make_button(cy + 25, "HIGH SCORES", "highscores")
    self._make_button(cy + 80, "SETTINGS", "settings")
    self._draw_buttons()

    self._draw_pixel_text(
      "ARROWS / WASD — MOVE   ESC — MENU",
      self.win_w // 2,
      self.win_h - 36,
      self.font_xs,
      COL_DIM,
      center_x=True,
    )

  def _draw_play(self) -> None:
    self._draw_hud()
    self._draw_grid()
    self._draw_apple()
    self._draw_snake()
    if self.screen_id == Screen.PAUSED:
      self._draw_overlay()
      self._draw_pixel_text("PAUSED", self.win_w // 2, self.win_h // 2 - 20, self.font_lg, COL_ACCENT, center_x=True)
      self._make_button(self.win_h // 2 + 20, "RESUME", "resume")
      self._make_button(self.win_h // 2 + 75, "QUIT TO TITLE", "title")
      self._draw_buttons()

  def _draw_game_over(self) -> None:
    self._draw_overlay()
    self._draw_pixel_text("GAME OVER", self.win_w // 2, 120, self.font_lg, COL_APPLE, center_x=True)
    self._draw_pixel_text(
      f"SCORE {self.score}",
      self.win_w // 2,
      175,
      self.font_md,
      COL_TEXT,
      center_x=True,
    )
    if self.score >= self.highscore and self.score > 0:
      self._draw_pixel_text("NEW HIGH SCORE!", self.win_w // 2, 210, self.font_sm, COL_ACCENT, center_x=True)
    self._make_button(self.win_h - 160, "RETRY", "retry")
    self._make_button(self.win_h - 105, "TITLE", "title")
    self._draw_buttons()

  def _draw_highscores(self) -> None:
    pygame.draw.rect(self.screen, COL_ACCENT, (30, 40, self.win_w - 60, self.win_h - 80), 2)
    self._draw_pixel_text("HIGH SCORES", self.win_w // 2, 60, self.font_lg, COL_ACCENT, center_x=True)
    self._draw_pixel_text(f"BEST: {self.highscore}", self.win_w // 2, 105, self.font_md, COL_TEXT, center_x=True)
    y = 145
    for i, s in enumerate(self.score_history[:8]):
      rank = f"{i + 1}."
      self._draw_pixel_text(rank, 80, y, self.font_sm, COL_DIM)
      self._draw_pixel_text(f"{s:04d}", self.win_w // 2, y, self.font_sm, COL_TEXT, center_x=True)
      y += 28
    if not self.score_history:
      self._draw_pixel_text("NO SCORES YET", self.win_w // 2, 180, self.font_sm, COL_DIM, center_x=True)
    self._make_button(self.win_h - 90, "BACK", "title")
    self._draw_buttons()

  def _draw_settings(self) -> None:
    pygame.draw.rect(self.screen, COL_ACCENT, (30, 40, self.win_w - 60, self.win_h - 80), 2)
    self._draw_pixel_text("SETTINGS", self.win_w // 2, 50, self.font_lg, COL_ACCENT, center_x=True)

    toggles = [
      ("sfx", "SOUND FX", self.settings.get("sfx", True)),
      ("show_grid", "SHOW GRID", self.settings.get("show_grid", True)),
    ]
    y = 100
    for key, label, on in toggles:
      self._draw_pixel_text(label, 50, y, self.font_sm, COL_TEXT)
      btn_label = "ON" if on else "OFF"
      self._make_button(y - 6, btn_label, f"toggle_{key}", w=80, h=30)
      rect, lbl, act = self._buttons[-1]
      rect.x = self.win_w - 120
      rect.y = y - 6
      y += 42

    map_id = self.settings.get("map_size", "small")
    map_lbl = MAP_LABELS.get(map_id, "SMALL")
    gw, gh, _ = MAP_PRESETS[map_id]
    self._draw_pixel_text("MAP SIZE", 50, y, self.font_sm, COL_TEXT)
    self._make_button(y - 6, map_lbl, "cycle_map", w=100, h=30)
    rect, lbl, act = self._buttons[-1]
    rect.x = self.win_w - 120
    rect.y = y - 6
    y += 42
    self._draw_pixel_text(f"{gw}x{gh} cells", 50, y, self.font_xs, COL_DIM)

    self._make_button(self.win_h - 70, "BACK", "title")
    self._draw_buttons()

  # --- input ---

  def _hit_button(self, pos: Tuple[int, int]) -> Optional[str]:
    for rect, _, action in self._buttons:
      if rect.collidepoint(pos):
        return action
    return None

  def handle_event(self, event: pygame.event.Event) -> None:
    if event.type == pygame.MOUSEMOTION:
      self._hover = self._hit_button(event.pos)

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
      action = self._hit_button(event.pos)
      if action:
        self._do_action(action)
        self.audio.play_sfx(self.audio.ui)
      return

    if event.type != pygame.KEYDOWN:
      return

    if event.key == pygame.K_ESCAPE:
      if self.screen_id == Screen.PLAYING:
        self.screen_id = Screen.PAUSED
      elif self.screen_id == Screen.PAUSED:
        self.screen_id = Screen.PLAYING
      elif self.screen_id in (Screen.HIGHSCORES, Screen.SETTINGS):
        self.screen_id = Screen.TITLE
      elif self.screen_id == Screen.GAME_OVER:
        self.screen_id = Screen.TITLE
      return

    if self.screen_id == Screen.TITLE and event.key in (pygame.K_RETURN, pygame.K_SPACE):
      self.start_game()
      self.audio.play_sfx(self.audio.ui)
      return

    if self.screen_id == Screen.GAME_OVER and event.key == pygame.K_RETURN:
      self.start_game()
      return

    if self.screen_id in (Screen.PLAYING, Screen.PAUSED):
      if event.key == pygame.K_p:
        self.screen_id = (
          Screen.PAUSED if self.screen_id == Screen.PLAYING else Screen.PLAYING
        )
      if self.screen_id != Screen.PLAYING:
        return
      if event.key in DIRS:
        nd = DIRS[event.key]
        if (nd[0], nd[1]) != (-self.direction[0], -self.direction[1]):
          self.next_direction = nd

  def _do_action(self, action: str) -> None:
    if action == "play" or action == "retry":
      self.start_game()
    elif action == "highscores":
      self.screen_id = Screen.HIGHSCORES
    elif action == "settings":
      self.screen_id = Screen.SETTINGS
    elif action == "title":
      self.screen_id = Screen.TITLE
    elif action == "resume":
      self.screen_id = Screen.PLAYING
    elif action == "cycle_map":
      cur = self.settings.get("map_size", "small")
      idx = MAP_ORDER.index(cur) if cur in MAP_ORDER else 0
      nxt = MAP_ORDER[(idx + 1) % len(MAP_ORDER)]
      in_game = self.screen_id in (Screen.PLAYING, Screen.PAUSED)
      if not in_game:
        self._apply_map_size(nxt, resize_now=True)
      else:
        self.settings["map_size"] = nxt
      self._save_settings()
    elif action.startswith("toggle_"):
      key = action[7:]
      self.settings[key] = not self.settings.get(key, True)
      if key == "sfx":
        self.audio.sfx_on = self.settings["sfx"]
      self._save_settings()

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
  game = SnakeGame()
  game.run()


if __name__ == "__main__":
  main()
