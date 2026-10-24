#!/usr/bin/env python3
"""Minimal self-check for marfabot formatting / ban helpers."""

from __future__ import annotations

import os
import tempfile

from artalk_api import ArtalkError, mint_admin_jwt, lookup_admin_user_id
from ban import ban_email, is_email_banned, normalize_email
from format import build_keyboard, comment_link, format_message, parse_callback
from main import format_callback_error, merge_flags, raw_content
from telegram_api import TelegramClient


def main() -> None:
    assert normalize_email("  A@B.C ") == "a@b.c"

    token = mint_admin_jwt("test-key", 1, ttl_sec=60)
    parts = token.split(".")
    assert len(parts) == 3

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "banned_emails.txt")
        assert ban_email(path, "Spam@Example.com") is True
        assert ban_email(path, "spam@example.com") is False
        assert is_email_banned(path, "SPAM@example.com")
        assert not is_email_banned(path, "ok@example.com")

        db = os.path.join(td, "artalk.db")
        import sqlite3

        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, is_admin INTEGER)"
        )
        conn.execute(
            "INSERT INTO users (id, name, email, is_admin) VALUES (9, 'admin', 'a@b.c', 1)"
        )
        conn.commit()
        conn.close()
        assert lookup_admin_user_id(db, "a@b.c") == 9

    comment = {
        "id": 42,
        "nick": "Alice",
        "email": "a@example.com",
        "content_raw": "Hello world",
        "is_pending": True,
        "is_collapsed": False,
        "is_pinned": False,
        "page_url": "https://blog.example.com/post/",
        "page_key": "/post/",
        "site_name": "Blog",
        "rid": 0,
        "user_id": 7,
    }
    text = format_message(comment)
    assert "Alice" in text
    assert "a@example.com" in text
    assert "Hello world" in text
    assert "[Pending]" in text
    assert "atk_comment=42" in comment_link(comment)

    kb = build_keyboard(comment, sidebar_url="https://comments.example.com")
    flat = [b for row in kb["inline_keyboard"] for b in row]
    texts = {b["text"] for b in flat}
    assert "Одобрить" in texts
    assert "Свернуть" in texts
    assert "Закрепить" in texts
    assert "Удалить" in texts
    assert "Забанить" in texts
    assert any(b.get("url") for b in flat)

    assert parse_callback("p:42") == ("p", 42)
    assert parse_callback("d!:99") == ("d!", 99)
    assert parse_callback("b!:1") == ("b!", 1)
    assert parse_callback("x:5") == ("x", 5)

    approved = {**comment, "is_pending": False}
    kb2 = build_keyboard(approved, sidebar_url="https://comments.example.com")
    texts2 = {b["text"] for row in kb2["inline_keyboard"] for b in row}
    assert "В pending" in texts2

    # Prefer content_raw over webhook HTML content
    webhookish = {
        "id": 1,
        "content": "<p>Hello</p>",
        "content_raw": "Hello",
        "is_pending": True,
    }
    live = {"id": 1, "content": "Hello", "is_pending": True, "page_key": "/p", "site_name": "S"}
    merged = merge_flags(webhookish, live)
    assert raw_content(merged) == "Hello"
    assert "<p>" not in raw_content(merged)

    live_only = merge_flags({}, {"id": 2, "content": "raw md", "is_pending": False})
    assert raw_content(live_only) == "raw md"

    err = ArtalkError("Artalk PUT failed: 400", 400, '{"msg":"bad"}')
    tip = format_callback_error(err)
    assert "400" in tip or "bad" in tip or "Artalk" in tip
    assert len(tip) <= 180

    # message is not modified must not raise
    import urllib.error
    import urllib.request

    real_urlopen = urllib.request.urlopen

    def _http_error_factory() -> urllib.error.HTTPError:
        err = urllib.error.HTTPError(
            "https://api.telegram.org",
            400,
            "Bad Request",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        err.read = lambda: b'{"ok":false,"description":"Bad Request: message is not modified"}'  # type: ignore[method-assign]
        return err

    def fake_urlopen_not_modified(*args: object, **kwargs: object) -> object:
        raise _http_error_factory()

    urllib.request.urlopen = fake_urlopen_not_modified  # type: ignore[assignment]
    try:
        tg = TelegramClient("000:fake")
        assert tg.edit_message_text(1, 2, "same") == {}
    finally:
        urllib.request.urlopen = real_urlopen  # type: ignore[assignment]

    print("marfabot self_check: ok")


if __name__ == "__main__":
    main()
