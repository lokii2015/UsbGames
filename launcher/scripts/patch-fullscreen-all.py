#!/usr/bin/env python3
"""Patch UsbGames pygame titles for default fullscreen + scaled canvas."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "PortableGames"

HELPER = '''
def _present_display(_display, _canvas):
    sw, sh = _display.get_size()
    cw, ch = _canvas.get_size()
    if sw == cw and sh == ch:
        _display.blit(_canvas, (0, 0))
    else:
        _display.blit(pygame.transform.smoothscale(_canvas, (sw, sh)), (0, 0))
    pygame.display.flip()


def _map_mouse(_display, pos, lw, lh):
    sw, sh = _display.get_size()
    if sw <= 0 or sh <= 0:
        return pos
    return int(pos[0] * lw / sw), int(pos[1] * lh / sh)
'''

GAMES = [
    ("BrickBreaker", "brick_breaker_game.py", "WIN_W", "WIN_H"),
    ("SpaceCommand", "space_command_game.py", "WIN_W", "WIN_H"),
    ("MemoryMatch", "memory_match_game.py", "WIN_W", "WIN_H"),
    ("PixelFlap", "pixel_flap_game.py", "WIN_W", "WIN_H"),
    ("TicTacToe", "tictactoe_game.py", "WIN_W", "WIN_H"),
]


def patch_file(folder: str, filename: str, wname: str, hname: str) -> None:
    path = ROOT / folder / filename
    if not path.exists():
        print("skip", path)
        return
    text = path.read_text(encoding="utf-8")
    if "_present_display" in text:
        print("already", path)
        return
    if "def _present_display" not in text:
        # insert after FPS_CAP or WIN_H line block
        marker = f"{hname} = "
        idx = text.find(marker)
        if idx < 0:
            print("no marker", path)
            return
        line_end = text.find("\n", idx)
        text = text[: line_end + 1] + HELPER + text[line_end + 1 :]

    text = text.replace(
        "self.screen = pygame.display.set_mode((WIN_W, WIN_H))",
        "self._fullscreen = True\n        self._display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)\n        self.screen = pygame.Surface((WIN_W, WIN_H))",
    )
    text = text.replace("pygame.display.flip()", "_present_display(self._display, self.screen)")

    # mouse map
    text = text.replace("event.pos)", " _map_mouse(self._display, event.pos, WIN_W, WIN_H))")
    # fix double map - only for collidepoint/hit_btn - too broad

    path.write_text(text, encoding="utf-8")
    print("patched", path)


if __name__ == "__main__":
    for g in GAMES:
        patch_file(*g)
