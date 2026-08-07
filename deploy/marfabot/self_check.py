#!/usr/bin/env python3
"""Minimal self-check for marfabot formatting / ban helpers."""

from __future__ import annotations

import os
import tempfile

from artalk_api import mint_admin_jwt, lookup_admin_user_id
from ban import ban_email, is_email_banned, normalize_email
from format import build_keyboard, comment_link, format_message, parse_callback


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

    print("marfabot self_check: ok")


if __name__ == "__main__":
    main()
