#!/usr/bin/env python3
"""UsbGames Black Jack — retro casino card game."""

from __future__ import annotations

import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame

GAME_ID = "BlackJack"
WIN_W, WIN_H = 480, 640
FPS_CAP = 60
HUD_H = 44
START_CHIPS = 1000
SAMPLE_RATE = 22050

COL_BG = (12, 28, 18)
COL_FELT = (18, 72, 42)
COL_TURQ = (64, 224, 208)
COL_GOLD = (255, 220, 80)
COL_TEXT = (220, 235, 230)
COL_DIM = (90, 105, 115)
COL_BTN = (22, 28, 40)
COL_BTN_HOVER = (34, 46, 52)
COL_RED = (220, 60, 70)
COL_BLACK = (30, 30, 40)

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def usb_root() -> Optional[str]:
    d = app_dir()
    if os.path.basename(d).lower() in ("blackjack", "black-jack"):
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
            self.deal = _tone(380, 40, 0.18)
            self.chip = _tone(520, 30, 0.2)
            self.win = _tone(660, 100, 0.28)
            self.lose = _tone(180, 120, 0.25)
            self.ui = _tone(480, 35, 0.2)
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
    default = {"hands_won": 0, "hands_lost": 0, "blackjacks": 0, "best_chips": START_CHIPS}
    data = load_json(STATS_LOCAL, default)
    prof = profile_path()
    if prof and os.path.isfile(prof):
        try:
            with open(prof, "r", encoding="utf-8") as f:
                root = json.load(f)
            g = root.get("games", {}).get(GAME_ID, {})
            for k in default:
                if k in g:
                    if k == "best_chips":
                        data[k] = max(int(data.get(k, 0)), int(g[k]))
                    else:
                        data[k] = max(int(data.get(k, 0)), int(g[k]))
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
    rank: str
    suit: str

    def value(self) -> int:
        if self.rank in ("J", "Q", "K"):
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    def is_red(self) -> bool:
        return self.suit in ("♥", "♦")


def hand_value(cards: List[Card]) -> int:
    total = sum(c.value() for c in cards)
    aces = sum(1 for c in cards if c.rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def new_deck() -> List[Card]:
    deck = [Card(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


class Screen(Enum):
    TITLE = auto()
    BETTING = auto()
    PLAYING = auto()
    DEALER_TURN = auto()
    ROUND_OVER = auto()
    SETTINGS = auto()


class BlackJackGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Black Jack — UsbGames")
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
        self.chips = START_CHIPS
        self.bet = 25
        self.deck: List[Card] = []
        self.player: List[Card] = []
        self.dealer: List[Card] = []
        self.dealer_hidden = True
        self.message = ""
        self.round_timer = 0.0
        self.dealer_timer = 0.0
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

    def _make_btn(self, y: int, label: str, action: str, w: int = 200) -> None:
        self._buttons.append((pygame.Rect(WIN_W // 2 - w // 2, y, w, 36), label, action))

    def _draw_buttons(self) -> None:
        for rect, label, action in self._buttons:
            hover = self._hover == action
            pygame.draw.rect(self.screen, COL_BTN_HOVER if hover else COL_BTN, rect)
            pygame.draw.rect(self.screen, COL_GOLD if hover else COL_DIM, rect, 2)
            self._pixel_text(label, rect.centerx, rect.centery - 8, self.font_sm, COL_TEXT, center=True)

    def _draw_card(self, card: Card, x: int, y: int, hidden: bool = False) -> None:
        w, h = 52, 72
        pygame.draw.rect(self.screen, (240, 240, 245) if not hidden else COL_BTN, (x, y, w, h), border_radius=4)
        pygame.draw.rect(self.screen, COL_GOLD, (x, y, w, h), 2, border_radius=4)
        if hidden:
            pygame.draw.line(self.screen, COL_DIM, (x + 8, y + 8), (x + w - 8, y + h - 8), 2)
            pygame.draw.line(self.screen, COL_DIM, (x + w - 8, y + 8), (x + 8, y + h - 8), 2)
            return
        col = COL_RED if card.is_red() else COL_BLACK
        self._pixel_text(card.rank, x + 8, y + 6, self.font_md, col)
        self._pixel_text(card.suit, x + 8, y + 28, self.font_sm, col)

    def _deal_round(self) -> None:
        if self.chips < self.bet:
            self.bet = max(10, self.chips)
        if self.chips < 10:
            self.chips = START_CHIPS
            self.message = "Rebuy — fresh chips!"
        self.chips -= self.bet
        self.deck = new_deck()
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.dealer_hidden = True
        self.message = ""
        self.audio.play(self.audio.deal)
        pv, dv = hand_value(self.player), hand_value(self.dealer)
        if pv == 21 or dv == 21:
            self.dealer_hidden = False
            self._resolve_round()
        else:
            self.screen_id = Screen.PLAYING

    def _resolve_round(self) -> None:
        self.dealer_hidden = False
        pv = hand_value(self.player)
        dv = hand_value(self.dealer)
        payout = 0
        if pv > 21:
            self.message = "BUST — you lose"
            self.stats["hands_lost"] = int(self.stats.get("hands_lost", 0)) + 1
            self.audio.play(self.audio.lose)
        elif dv > 21:
            payout = self.bet * 2
            self.message = "DEALER BUST — you win!"
            self.stats["hands_won"] = int(self.stats.get("hands_won", 0)) + 1
            self.audio.play(self.audio.win)
        elif pv == 21 and len(self.player) == 2:
            payout = int(self.bet * 2.5)
            self.message = "BLACKJACK!"
            self.stats["blackjacks"] = int(self.stats.get("blackjacks", 0)) + 1
            self.stats["hands_won"] = int(self.stats.get("hands_won", 0)) + 1
            self.audio.play(self.audio.win)
        elif pv > dv:
            payout = self.bet * 2
            self.message = "YOU WIN"
            self.stats["hands_won"] = int(self.stats.get("hands_won", 0)) + 1
            self.audio.play(self.audio.win)
        elif pv < dv:
            self.message = "DEALER WINS"
            self.stats["hands_lost"] = int(self.stats.get("hands_lost", 0)) + 1
            self.audio.play(self.audio.lose)
        else:
            payout = self.bet
            self.message = "PUSH"
        self.chips += payout
        self.stats["best_chips"] = max(int(self.stats.get("best_chips", 0)), self.chips)
        save_stats(self.stats)
        self.screen_id = Screen.ROUND_OVER
        self.round_timer = 2.5

    def _dealer_play(self) -> None:
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        self._resolve_round()

    def update(self, dt: float) -> None:
        if self.screen_id == Screen.ROUND_OVER:
            self.round_timer -= dt
            if self.round_timer <= 0:
                self.screen_id = Screen.BETTING
        elif self.screen_id == Screen.DEALER_TURN:
            self.dealer_timer -= dt
            if self.dealer_timer <= 0:
                self._dealer_play()

    def draw(self) -> None:
        self.screen.fill(COL_BG)
        pygame.draw.rect(self.screen, COL_FELT, (12, HUD_H + 8, WIN_W - 24, WIN_H - HUD_H - 20), border_radius=8)
        self._buttons.clear()

        if self.screen_id == Screen.TITLE:
            self._pixel_text("BLACK JACK", WIN_W // 2, 100, self.font_lg, COL_GOLD, center=True)
            self._pixel_text("UsbGames", WIN_W // 2, 150, self.font_sm, COL_DIM, center=True)
            bj = int(self.stats.get("blackjacks", 0))
            self._pixel_text(f"BLACKJACKS {bj}", WIN_W // 2, 210, self.font_md, COL_TURQ, center=True)
            self._make_btn(280, "PLAY", "play")
            self._make_btn(335, "SETTINGS", "settings")
            self._draw_buttons()
        elif self.screen_id in (Screen.BETTING, Screen.PLAYING, Screen.DEALER_TURN, Screen.ROUND_OVER):
            self._pixel_text(f"CHIPS ${self.chips}", 16, 10, self.font_sm, COL_GOLD)
            self._pixel_text(f"BET ${self.bet}", WIN_W - 16, 10, self.font_sm, COL_TEXT, center=True)
            self._pixel_text("DEALER", WIN_W // 2, HUD_H + 24, self.font_xs, COL_DIM, center=True)
            dx = WIN_W // 2 - 60
            for i, c in enumerate(self.dealer):
                self._draw_card(c, dx + i * 58, HUD_H + 44, hidden=(i == 1 and self.dealer_hidden))
            if not self.dealer_hidden and self.dealer:
                self._pixel_text(str(hand_value(self.dealer)), WIN_W // 2, HUD_H + 130, self.font_md, COL_TEXT, center=True)
            self._pixel_text("YOU", WIN_W // 2, 340, self.font_xs, COL_DIM, center=True)
            px = WIN_W // 2 - 60
            for i, c in enumerate(self.player):
                self._draw_card(c, px + i * 58, 368)
            if self.player:
                self._pixel_text(str(hand_value(self.player)), WIN_W // 2, 460, self.font_md, COL_TURQ, center=True)
            if self.message:
                self._pixel_text(self.message, WIN_W // 2, 500, self.font_md, COL_GOLD, center=True)

            if self.screen_id == Screen.BETTING:
                for i, (label, act) in enumerate([
                    ("$10", "bet10"), ("$25", "bet25"), ("$50", "bet50"), ("$100", "bet100"),
                ]):
                    x = 24 + i * 112
                    self._buttons.append((pygame.Rect(x, 518, 100, 36), f"BET {label}", act))
                self._make_btn(575, "DEAL", "deal", 180)
                self._make_btn(620, "MENU", "title", 140)
                self._draw_buttons()
            elif self.screen_id == Screen.PLAYING:
                self._buttons.append((pygame.Rect(40, 548, 120, 36), "HIT", "hit"))
                self._buttons.append((pygame.Rect(180, 548, 120, 36), "STAND", "stand"))
                self._buttons.append((pygame.Rect(320, 548, 120, 36), "DOUBLE", "double"))
                self._draw_buttons()
            elif self.screen_id == Screen.ROUND_OVER:
                self._make_btn(600, "NEXT HAND", "next", 180)
                self._draw_buttons()
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
        if action == "play":
            self.chips = max(self.chips, START_CHIPS) if self.chips < 10 else self.chips
            self.screen_id = Screen.BETTING
        elif action.startswith("bet"):
            amounts = {"bet10": 10, "bet25": 25, "bet50": 50, "bet100": 100}
            self.bet = min(amounts.get(action, 25), self.chips)
            self.audio.play(self.audio.chip)
        elif action == "deal":
            self._deal_round()
        elif action == "hit":
            if self.screen_id == Screen.PLAYING:
                self.player.append(self.deck.pop())
                self.audio.play(self.audio.deal)
                if hand_value(self.player) > 21:
                    self._resolve_round()
        elif action == "stand":
            if self.screen_id == Screen.PLAYING:
                self.screen_id = Screen.DEALER_TURN
                self.dealer_timer = 0.4
        elif action == "double":
            if self.screen_id == Screen.PLAYING and self.chips >= self.bet:
                self.chips -= self.bet
                self.bet *= 2
                self.player.append(self.deck.pop())
                self.audio.play(self.audio.deal)
                if hand_value(self.player) > 21:
                    self._resolve_round()
                else:
                    self.screen_id = Screen.DEALER_TURN
                    self.dealer_timer = 0.4
        elif action == "next":
            self.screen_id = Screen.BETTING
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
            self.screen_id = Screen.TITLE if self.screen_id != Screen.TITLE else Screen.TITLE
        if event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.screen_id == Screen.TITLE:
            self._do_action("play")

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
    BlackJackGame().run()


if __name__ == "__main__":
    main()
