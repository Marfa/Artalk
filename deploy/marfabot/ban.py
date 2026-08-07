"""Ban-list file helpers."""

from __future__ import annotations

import os
import threading

_lock = threading.Lock()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_email_banned(path: str, email: str) -> bool:
    norm = normalize_email(email)
    if not norm or not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if normalize_email(line) == norm:
                return True
    return False


def ban_email(path: str, email: str) -> bool:
    """Append email to ban file if not already present. Returns True if appended."""
    norm = normalize_email(email)
    if not norm:
        return False
    with _lock:
        if is_email_banned(path, norm):
            return False
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(norm + "\n")
        return True
