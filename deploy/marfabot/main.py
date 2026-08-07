"""Artalk → Telegram moderation bot (@marfabot).

Receives admin webhooks from Artalk, sends rich notifications with inline
moderation buttons, and applies actions via Artalk Admin API.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from artalk_api import ArtalkClient, ArtalkError
from ban import ban_email, normalize_email
from format import build_keyboard, format_message, parse_callback
from telegram_api import TelegramClient, TelegramError

log = logging.getLogger("marfabot")

# comment_id -> last known webhook comment snapshot (email, flags, …)
_store: dict[int, dict[str, Any]] = {}
_store_lock = threading.Lock()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = env(name)
    if not raw:
        return default
    return int(raw)


def remember(comment: dict[str, Any]) -> None:
    cid = int(comment["id"])
    with _store_lock:
        _store[cid] = comment


def recall(comment_id: int) -> dict[str, Any] | None:
    with _store_lock:
        cached = _store.get(comment_id)
        return dict(cached) if cached else None


def merge_flags(cached: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    """Prefer live flags from GET; keep email/content_raw from webhook cache."""
    out = {**cached, **live}
    if cached.get("email"):
        out["email"] = cached["email"]
    if cached.get("content_raw"):
        out["content_raw"] = cached["content_raw"]
    if cached.get("nick") and not out.get("nick"):
        out["nick"] = cached["nick"]
    return out


class App:
    def __init__(self) -> None:
        self.hook_secret = env("MARFABOT_HOOK_SECRET")
        if not self.hook_secret:
            raise SystemExit("MARFABOT_HOOK_SECRET is required")

        token = env("TELEGRAM_BOT_TOKEN") or env("MARFABOT_TELEGRAM_TOKEN")
        if not token:
            raise SystemExit("TELEGRAM_BOT_TOKEN is required")

        self.chat_id = env_int("MARFABOT_CHAT_ID", 0)
        if not self.chat_id:
            raise SystemExit("MARFABOT_CHAT_ID is required")

        allow = env("MARFABOT_ALLOWED_USER_IDS", str(self.chat_id))
        self.allowed_users = {int(x) for x in allow.split(",") if x.strip()}

        artalk_url = env("ARTALK_API_URL", "http://artalk:23366")
        admin_email = env("ARTALK_ADMIN_EMAIL")
        admin_password = env("ARTALK_ADMIN_PASSWORD")
        admin_name = env("ARTALK_ADMIN_NAME", "")
        app_key = env("ATK_APP_KEY")
        db_path = env("ARTALK_DB_PATH", "/data/artalk.db")
        if not admin_password and not app_key:
            raise SystemExit("ARTALK_ADMIN_PASSWORD or ATK_APP_KEY is required")

        self.ban_file = env("MARFABOT_BAN_FILE", "/data/banned_emails.txt")
        self.sidebar_url = env("MARFABOT_SIDEBAR_URL", "https://comments.themarfa.name")
        self.listen_host = env("MARFABOT_LISTEN_HOST", "0.0.0.0")
        self.listen_port = env_int("MARFABOT_LISTEN_PORT", 8086)

        self.tg = TelegramClient(token)
        self.artalk = ArtalkClient(
            artalk_url,
            admin_email,
            admin_password,
            admin_name,
            app_key=app_key,
            db_path=db_path,
        )
        self._admin_emails: set[str] | None = None

    def admin_emails(self) -> set[str]:
        if self._admin_emails is None:
            try:
                self._admin_emails = self.artalk.find_admin_emails()
            except ArtalkError as e:
                log.warning("could not load admin emails: %s", e)
                self._admin_emails = set()
            cfg = normalize_email(env("ARTALK_ADMIN_EMAIL"))
            if cfg:
                self._admin_emails.add(cfg)
        return self._admin_emails

    def handle_webhook(self, payload: dict[str, Any]) -> None:
        comment = payload.get("comment")
        if not isinstance(comment, dict) or not comment.get("id"):
            raise ValueError("webhook missing comment.id")
        remember(comment)
        text = format_message(comment)
        kb = build_keyboard(comment, sidebar_url=self.sidebar_url)
        self.tg.send_message(self.chat_id, text, kb)

    def _load_comment(self, comment_id: int) -> dict[str, Any]:
        cached = recall(comment_id) or {}
        try:
            live = self.artalk.get_comment(comment_id)
        except ArtalkError:
            if not cached:
                raise
            return cached
        merged = merge_flags(cached, live)
        remember(merged)
        return merged

    def _put_flags(self, comment: dict[str, Any], **flags: bool) -> dict[str, Any]:
        payload = {
            "content": comment.get("content_raw") or comment.get("content") or "",
            "page_key": comment.get("page_key") or "",
            "site_name": comment.get("site_name") or "",
            "rid": int(comment.get("rid") or 0),
            "is_collapsed": bool(flags.get("is_collapsed", comment.get("is_collapsed"))),
            "is_pending": bool(flags.get("is_pending", comment.get("is_pending"))),
            "is_pinned": bool(flags.get("is_pinned", comment.get("is_pinned"))),
            "nick": comment.get("nick") or "",
            "email": comment.get("email") or "",
            "link": comment.get("link") or "",
        }
        if not payload["page_key"] or not payload["site_name"]:
            raise ArtalkError("comment missing page_key/site_name for update")
        updated = self.artalk.update_comment(int(comment["id"]), payload)
        # update response is cooked comment (no email) — merge
        merged = merge_flags(comment, updated if isinstance(updated, dict) else {})
        remember(merged)
        return merged

    def handle_callback(self, cq: dict[str, Any]) -> None:
        from_user = cq.get("from") or {}
        uid = int(from_user.get("id") or 0)
        if uid not in self.allowed_users:
            self.tg.answer_callback_query(cq["id"], "Нет доступа")
            return

        action, comment_id = parse_callback(cq.get("data") or "")
        msg = cq.get("message") or {}
        chat_id = int((msg.get("chat") or {}).get("id") or self.chat_id)
        message_id = int(msg.get("message_id") or 0)

        if comment_id is None:
            self.tg.answer_callback_query(cq["id"], "Некорректные данные")
            return

        try:
            if action == "x":
                comment = self._load_comment(comment_id)
                self.tg.edit_message_text(
                    chat_id,
                    message_id,
                    format_message(comment),
                    build_keyboard(comment, sidebar_url=self.sidebar_url),
                )
                self.tg.answer_callback_query(cq["id"], "Отменено")
                return

            if action == "d":
                comment = self._load_comment(comment_id)
                self.tg.edit_message_text(
                    chat_id,
                    message_id,
                    format_message(comment, footer="Удалить этот комментарий?"),
                    build_keyboard(comment, sidebar_url=self.sidebar_url, mode="confirm_delete"),
                )
                self.tg.answer_callback_query(cq["id"])
                return

            if action == "b":
                comment = self._load_comment(comment_id)
                self.tg.edit_message_text(
                    chat_id,
                    message_id,
                    format_message(
                        comment,
                        footer=(
                            "Забанить? Email больше не сможет комментировать; "
                            "пользователь и все его комментарии будут удалены."
                        ),
                    ),
                    build_keyboard(comment, sidebar_url=self.sidebar_url, mode="confirm_ban"),
                )
                self.tg.answer_callback_query(cq["id"])
                return

            if action == "d!":
                self.artalk.delete_comment(comment_id)
                with _store_lock:
                    _store.pop(comment_id, None)
                self.tg.edit_message_text(chat_id, message_id, f"Комментарий #{comment_id} удалён.")
                self.tg.answer_callback_query(cq["id"], "Удалено")
                return

            if action == "b!":
                comment = self._load_comment(comment_id)
                email = normalize_email(comment.get("email") or "")
                user_id = int(comment.get("user_id") or 0)
                if email and email in self.admin_emails():
                    self.tg.answer_callback_query(cq["id"], "Нельзя банить админа")
                    return
                if email:
                    ban_email(self.ban_file, email)
                if user_id:
                    self.artalk.delete_user(user_id)
                else:
                    self.artalk.delete_comment(comment_id)
                with _store_lock:
                    _store.pop(comment_id, None)
                self.tg.edit_message_text(
                    chat_id,
                    message_id,
                    f"Забанен {email or '—'}; пользователь #{user_id or '—'} удалён.",
                )
                self.tg.answer_callback_query(cq["id"], "Забанен")
                return

            comment = self._load_comment(comment_id)
            if action == "p":
                comment = self._put_flags(comment, is_pending=not bool(comment.get("is_pending")))
                tip = "Одобрено" if not comment.get("is_pending") else "В pending"
            elif action == "c":
                comment = self._put_flags(comment, is_collapsed=not bool(comment.get("is_collapsed")))
                tip = "Свёрнуто" if comment.get("is_collapsed") else "Развёрнуто"
            elif action == "i":
                comment = self._put_flags(comment, is_pinned=not bool(comment.get("is_pinned")))
                tip = "Закреплено" if comment.get("is_pinned") else "Откреплено"
            else:
                self.tg.answer_callback_query(cq["id"], "Неизвестное действие")
                return

            self.tg.edit_message_text(
                chat_id,
                message_id,
                format_message(comment),
                build_keyboard(comment, sidebar_url=self.sidebar_url),
            )
            self.tg.answer_callback_query(cq["id"], tip)
        except (ArtalkError, TelegramError, ValueError, KeyError) as e:
            log.exception("callback failed")
            try:
                self.tg.answer_callback_query(cq["id"], f"Ошибка: {e}"[:180])
            except TelegramError:
                pass


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            log.info("%s - %s", self.address_string(), fmt % args)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/healthz", "/"):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            expected = f"/hook/{app.hook_secret}"
            if self.path != expected:
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                app.handle_webhook(payload)
            except Exception as e:
                log.exception("webhook error")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"msg": str(e)}).encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

    return Handler


def poll_loop(app: App) -> None:
    try:
        app.tg.delete_webhook()
    except TelegramError as e:
        log.warning("deleteWebhook: %s", e)
    offset: int | None = None
    while True:
        try:
            updates = app.tg.get_updates(offset, timeout=25)
            for u in updates:
                offset = int(u["update_id"]) + 1
                cq = u.get("callback_query")
                if cq:
                    app.handle_callback(cq)
        except Exception:
            log.exception("poll error")
            time.sleep(3)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = App()
    t = threading.Thread(target=poll_loop, args=(app,), name="tg-poll", daemon=True)
    t.start()
    server = ThreadingHTTPServer((app.listen_host, app.listen_port), make_handler(app))
    log.info("listening on %s:%s", app.listen_host, app.listen_port)
    server.serve_forever()


if __name__ == "__main__":
    main()
