"""Shared display helpers — logical 480×640 canvas scaled to fullscreen."""

from __future__ import annotations

import pygame

LOG_W, LOG_H = 480, 640


class FullscreenDisplay:
    """Draw to a fixed logical surface; scale to monitor on present."""

    def __init__(self, caption: str, start_fullscreen: bool = True) -> None:
        pygame.display.set_caption(caption)
        self.logical = pygame.Surface((LOG_W, LOG_H))
        self.fullscreen = start_fullscreen
        self.windowed_size = (LOG_W, LOG_H)
        if start_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size)

    @property
    def surf(self) -> pygame.Surface:
        """Surface games should draw onto."""
        return self.logical

    def toggle(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size)

    def present(self) -> None:
        sw, sh = self.screen.get_size()
        if sw == LOG_W and sh == LOG_H:
            self.screen.blit(self.logical, (0, 0))
        else:
            scaled = pygame.transform.smoothscale(self.logical, (sw, sh))
            self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

    def map_mouse(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Map screen coords to logical coords."""
        sw, sh = self.screen.get_size()
        if sw <= 0 or sh <= 0:
            return pos
        return int(pos[0] * LOG_W / sw), int(pos[1] * LOG_H / sh)
