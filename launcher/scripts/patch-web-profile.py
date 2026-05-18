#!/usr/bin/env python3
"""Insert _web_profile() helper into games that use USB profiles."""
from __future__ import annotations

import re
from pathlib import Path

PG = Path(__file__).resolve().parent.parent / "PortableGames"

HELPER = '''
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

'''

PROFILE_PATH_PATCH = re.compile(
    r"(def profile_path\(\)[^:]*:\n)(    root = usb_root\(\))",
    re.MULTILINE,
)

REPLACEMENT = r"\1    if _web_profile():\n        return None\n\2"


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "_web_profile()" in text:
        return False
    if "def profile_path()" not in text:
        return False
    insert_at = text.find("def profile_path()")
    if insert_at < 0:
        return False
    text = text[:insert_at] + HELPER + text[insert_at:]
    text, n = PROFILE_PATH_PATCH.subn(REPLACEMENT, text, count=1)
    if n != 1:
        print("warn profile_path patch:", path.name, n)
    text = text.replace(
        'self._pixel_text("Profile stats sync to UsbGames/profiles/"',
        'if not _web_profile():\n            self._pixel_text("Profile stats sync to UsbGames/profiles/"',
    )
    text = text.replace(
        'self._pixel_text("Synced to UsbGames profile"',
        'if not _web_profile():\n            self._pixel_text("Synced to UsbGames profile"',
    )
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    count = 0
    for py in PG.glob("*/*_game.py"):
        if patch_file(py):
            print("patched", py.parent.name)
            count += 1
    print("done,", count, "files")


if __name__ == "__main__":
    main()
