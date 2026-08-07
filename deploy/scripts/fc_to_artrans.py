#!/usr/bin/env python3
"""Convert FastComments JSONL export to Artalk Artrans JSON."""
import argparse
import datetime
import json
from email.utils import parsedate_to_datetime


def fmt_date(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        if v > 1e12:
            v = v / 1000
        dt = datetime.datetime.fromtimestamp(v, datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S %z")
    s = str(v)
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        pass
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S %z"
        )
    except Exception:
        return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--site-name", default="All-in-One Person")
    ap.add_argument("--site-url", default="https://blog.themarfa.name")
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(args.input) if l.strip()]
    ids = {str(c.get("id") or "") for c in rows}
    out = []
    for c in rows:
        page_key = c.get("url") or c.get("urlIdRaw") or c.get("urlId") or ""
        if page_key.startswith("http://"):
            page_key = "https://" + page_key[len("http://") :]
        if page_key and not page_key.endswith("/") and "?" not in page_key:
            page_key += "/"
        rid = str(c.get("parentId") or "0")
        if rid not in ("0", "") and rid not in ids:
            rid = "0"
        votes = c.get("votes") or {}
        up = c.get("votesUp")
        down = c.get("votesDown")
        if up is None and isinstance(votes, dict):
            up = votes.get("up") or 0
        if down is None and isinstance(votes, dict):
            down = votes.get("down") or 0
        out.append(
            {
                "id": str(c.get("id") or ""),
                "rid": rid,
                "content": c.get("comment") or "",
                "ua": "",
                "ip": "",
                "created_at": fmt_date(c.get("date")),
                "updated_at": fmt_date(c.get("date")),
                "is_collapsed": "false",
                "is_pending": "true"
                if (c.get("isSpam") and c.get("approved") is False)
                else "false",
                "is_pinned": "true" if c.get("isPinned") else "false",
                "vote_up": str(up or 0),
                "vote_down": str(down or 0),
                "nick": c.get("commenterName") or "Anonymous",
                "email": c.get("commenterEmail") or "",
                "link": "",
                "password": "",
                "badge_name": "",
                "badge_color": "",
                "page_key": page_key,
                "page_title": c.get("pageTitle") or "",
                "page_admin_only": "false",
                "site_name": args.site_name,
                "site_urls": args.site_url,
            }
        )
    json.dump(out, open(args.output, "w"), ensure_ascii=False)
    print(f"wrote {len(out)} comments -> {args.output}")


if __name__ == "__main__":
    main()
