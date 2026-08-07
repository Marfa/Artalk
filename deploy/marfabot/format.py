"""Message text and inline keyboard for moderation."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

TG_TEXT_LIMIT = 4096


def comment_link(comment: dict[str, Any]) -> str:
    page = comment.get("page") or {}
    base = (comment.get("page_url") or page.get("url") or "").strip()
    cid = comment.get("id")
    if not base:
        return ""
    if not cid:
        return base
    parsed = urlparse(base)
    q = parse_qs(parsed.query)
    q["atk_comment"] = [str(cid)]
    query = urlencode({k: v[0] for k, v in q.items()})
    return urlunparse(parsed._replace(query=query))


# Keep recursion out of truncation path
def format_message(comment: dict[str, Any], *, footer: str = "") -> str:
    nick = comment.get("nick") or "—"
    email = comment.get("email") or "—"
    raw = comment.get("content_raw") or comment.get("content") or ""
    link = comment_link(comment)

    head: list[str] = []
    if comment.get("is_pending"):
        head.extend(["[Pending]", ""])
    head.extend([f"Ник: {nick}", f"Почта: {email}", ""])
    head_text = "\n".join(head)
    tail_parts: list[str] = []
    if link:
        tail_parts.extend(["", link])
    if footer:
        tail_parts.extend(["", footer])
    tail = "\n".join(tail_parts)

    budget = TG_TEXT_LIMIT - len(head_text) - len(tail)
    body = raw
    if budget < 1:
        body = ""
    elif len(body) > budget:
        body = body[: max(0, budget - 1)] + "…"
    return head_text + body + tail


def _btn(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _url_btn(text: str, url: str) -> dict[str, str]:
    return {"text": text, "url": url}


def build_keyboard(
    comment: dict[str, Any],
    *,
    sidebar_url: str,
    mode: str = "main",
) -> dict[str, Any]:
    cid = int(comment["id"])
    if mode == "confirm_delete":
        return {
            "inline_keyboard": [
                [
                    _btn("Да, удалить", f"d!:{cid}"),
                    _btn("Отмена", f"x:{cid}"),
                ]
            ]
        }
    if mode == "confirm_ban":
        return {
            "inline_keyboard": [
                [
                    _btn("Да, забанить", f"b!:{cid}"),
                    _btn("Отмена", f"x:{cid}"),
                ]
            ]
        }

    pending_btn = "Одобрить" if comment.get("is_pending") else "В pending"
    collapse_btn = "Развернуть" if comment.get("is_collapsed") else "Свернуть"
    pin_btn = "Открепить" if comment.get("is_pinned") else "Закрепить"

    rows: list[list[dict[str, str]]] = [
        [
            _btn(pending_btn, f"p:{cid}"),
            _btn(collapse_btn, f"c:{cid}"),
            _btn(pin_btn, f"i:{cid}"),
        ],
        [
            _btn("Удалить", f"d:{cid}"),
            _btn("Забанить", f"b:{cid}"),
        ],
    ]
    link_row: list[dict[str, str]] = []
    page_link = comment_link(comment)
    if page_link:
        link_row.append(_url_btn("Открыть", page_link))
    if sidebar_url:
        link_row.append(_url_btn("Редактировать", sidebar_url))
    if link_row:
        rows.append(link_row)

    return {"inline_keyboard": rows}


def parse_callback(data: str) -> tuple[str, int | None]:
    """Return (action, comment_id). action examples: p, c, i, d, d!, b, b!, x."""
    if not data or ":" not in data:
        return data or "", None
    action, _, rest = data.partition(":")
    try:
        return action, int(rest)
    except ValueError:
        return action, None
