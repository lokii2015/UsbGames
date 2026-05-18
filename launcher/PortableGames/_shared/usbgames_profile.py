"""UsbGames profile mode — USB stick vs web account (downloads / launcher sync)."""
from __future__ import annotations

import json
import os
import sys
from typing import Optional, Tuple


def app_dir(caller_file: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(caller_file))


def usb_root_from(app_directory: str, folder_aliases: Tuple[str, ...]) -> Optional[str]:
    d = app_directory
    if os.path.basename(d).lower() in folder_aliases:
        parent = os.path.dirname(d)
        if os.path.basename(parent).lower() == "portablegames":
            return os.path.dirname(parent)
    return None


def is_web_profile(app_directory: str) -> bool:
    if os.environ.get("USBGAMES_PROFILE", "").strip().lower() == "web":
        return True
    meta_path = os.path.join(app_directory, "game.json")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("profile") == "web"
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def usb_profile_path(app_directory: str, folder_aliases: Tuple[str, ...]) -> Optional[str]:
    if is_web_profile(app_directory):
        return None
    root = usb_root_from(app_directory, folder_aliases)
    if not root:
        return None
    profiles = os.path.join(root, "UsbGames", "profiles")
    try:
        os.makedirs(profiles, exist_ok=True)
    except OSError:
        return None
    return os.path.join(profiles, "default.json")


def show_profile_hints(app_directory: str) -> bool:
    """In-game text about USB profiles — hidden for web/download builds."""
    return not is_web_profile(app_directory)
