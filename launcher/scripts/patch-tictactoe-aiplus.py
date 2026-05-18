"""Build TicTacToe AI+ from base TicTacToe source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "PortableGames"
src = (ROOT / "TicTacToe" / "tictactoe_game.py").read_text(encoding="utf-8")

AI_BLOCK = '''
def ai_move_medium(board: List[int]) -> int:
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


def ai_move_easy(board: List[int]) -> int:
    empties = [i for i, v in enumerate(board) if v == EMPTY]
    if random.random() < 0.35:
        return random.choice(empties)
    return ai_move_medium(board)


def _minimax(board: List[int], ai: int, hu: int, turn: int) -> int:
    w, _ = check_winner(board)
    if w == ai:
        return 10
    if w == hu:
        return -10
    if w == 0:
        return 0
    scores = []
    for i, v in enumerate(board):
        if v != EMPTY:
            continue
        board[i] = turn
        nxt = hu if turn == ai else ai
        scores.append(_minimax(board, ai, hu, nxt))
        board[i] = EMPTY
    return max(scores) if turn == ai else min(scores)


def ai_move_hard(board: List[int]) -> int:
    best, best_s = None, -999
    for i, v in enumerate(board):
        if v != EMPTY:
            continue
        board[i] = O_MARK
        s = _minimax(board, O_MARK, X_MARK, X_MARK)
        board[i] = EMPTY
        if s > best_s:
            best_s, best = s, i
    return best if best is not None else ai_move_medium(board)


def ai_move(board: List[int], level: str) -> int:
    if level == "easy":
        return ai_move_easy(board)
    if level == "hard":
        return ai_move_hard(board)
    return ai_move_medium(board)
'''

old_start = src.index("def ai_move(board")
old_end = src.index("def check_winner")
s = src[:old_start] + AI_BLOCK + "\n\n" + src[old_end:]

s = s.replace('GAME_ID = "TicTacToe"', 'GAME_ID = "TicTacToeAIPlus"\nAI_ORDER = ("easy", "medium", "hard")\nAI_LABELS = {"easy": "EASY", "medium": "MEDIUM", "hard": "HARD"}')
s = s.replace('("tictactoe", "tic-tac-toe")', '("tictactoe", "tic-tac-toe", "tictactoeaiplus")')
s = s.replace("Tic-Tac-Toe — UsbGames", "Tic-Tac-Toe AI+ — UsbGames")
s = s.replace('{"music": True, "sfx": True}', '{"music": True, "sfx": True, "ai_level": "medium"}')
s = s.replace(
    "        self._result_timer = 0.0\n\n    def _pixel_text",
    "        self._result_timer = 0.0\n        self._anim: dict[int, float] = {}\n        self.fullscreen = False\n\n    def _pixel_text",
)
s = s.replace(
    "        self.board[idx] = self.current\n        self.audio.play(self.audio.place)",
    "        self.board[idx] = self.current\n        self._anim[idx] = 0.0\n        self.audio.play(self.audio.place)",
)
s = s.replace(
    "        move = ai_move(self.board)",
    '        move = ai_move(self.board, self.settings.get("ai_level", "medium"))',
)
s = s.replace(
    "        self._fade += (self._fade_target - self._fade) * min(1.0, dt * 8)\n        if self._ai_thinking:",
    "        self._fade += (self._fade_target - self._fade) * min(1.0, dt * 8)\n        for k in list(self._anim):\n            self._anim[k] = min(1.0, self._anim[k] + dt * 4)\n        if self._ai_thinking:",
)
s = s.replace(
    "        rect = self._cell_rect(idx)\n        cx, cy = rect.center",
    "        rect = self._cell_rect(idx)\n        prog = self._anim.get(idx, 1.0)\n        scale = 0.35 + 0.65 * min(1.0, prog)\n        cx, cy = rect.center",
)
s = s.replace("            off = 22 + int(pulse * 4)", "            off = int((22 + int(pulse * 4)) * scale)")
s = s.replace("            r = 28 + int(pulse * 3)", "            r = int((28 + int(pulse * 3)) * scale)")
s = s.replace('"TIC-TAC-TOE"', '"TIC-TAC-TOE AI+"', 1)
s = s.replace("Medium AI · default", "AI level in Settings")
# settings AI cycle
s = s.replace(
    '        elif action.startswith("toggle_"):',
    '        elif action == "cycle_ai":\n            cur = self.settings.get("ai_level", "medium")\n            idx = AI_ORDER.index(cur) if cur in AI_ORDER else 0\n            self.settings["ai_level"] = AI_ORDER[(idx + 1) % len(AI_ORDER)]\n            self._save_settings()\n        elif action.startswith("toggle_"):',
)
s = s.replace(
    "        if event.type != pygame.KEYDOWN:\n            return\n        if event.key == pygame.K_ESCAPE:",
    "        if event.type != pygame.KEYDOWN:\n            return\n        if event.key == pygame.K_F11:\n            self.fullscreen = not self.fullscreen\n            self.screen = pygame.display.set_mode(\n                (WIN_W, WIN_H), pygame.FULLSCREEN if self.fullscreen else 0\n            )\n            return\n        if event.key == pygame.K_ESCAPE:",
)

out = ROOT / "TicTacToeAIPlus" / "tictactoe_aiplus_game.py"
out.write_text(s, encoding="utf-8")
print("Wrote", out)
