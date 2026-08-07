"""Artalk admin API client (stdlib urllib + optional JWT via app_key)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from typing import Any


class ArtalkError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def mint_admin_jwt(app_key: str, user_id: int, ttl_sec: int = 86400 * 3) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = _b64url(
        json.dumps(
            {"user_id": user_id, "iat": now, "exp": now + ttl_sec},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(app_key.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def lookup_admin_user_id(db_path: str, email: str = "", name: str = "") -> int:
    if not os.path.isfile(db_path):
        raise ArtalkError(f"Artalk DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if email:
            cur.execute(
                "SELECT id FROM users WHERE is_admin = 1 AND lower(email) = lower(?) LIMIT 1",
                (email,),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
        if name:
            cur.execute(
                "SELECT id FROM users WHERE is_admin = 1 AND lower(name) = lower(?) LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
        cur.execute("SELECT id FROM users WHERE is_admin = 1 ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise ArtalkError("no admin user in Artalk DB")
        return int(row[0])
    finally:
        conn.close()


class ArtalkClient:
    def __init__(
        self,
        base_url: str,
        email: str = "",
        password: str = "",
        name: str = "",
        *,
        app_key: str = "",
        db_path: str = "/data/artalk.db",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.name = name
        self.app_key = app_key
        self.db_path = db_path
        self._token: str | None = None
        self._token_exp: int = 0
        self._lock = threading.Lock()
        if not password and not app_key:
            raise ArtalkError("need ARTALK_ADMIN_PASSWORD or ATK_APP_KEY")

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        auth: bool = True,
        retry_auth: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if auth and retry_auth and e.code in (401, 403):
                with self._lock:
                    self._token = None
                    self._token_exp = 0
                return self._request(method, path, body, auth=auth, retry_auth=False)
            raise ArtalkError(f"Artalk {method} {path} failed: {e.code}", e.code, err_body) from e

    def _ensure_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_exp - 60:
                return self._token
        if self.password:
            payload: dict[str, str] = {"email": self.email, "password": self.password}
            if self.name:
                payload["name"] = self.name
            data = self._request(
                "POST", "/api/v2/user/access_token", payload, auth=False, retry_auth=False
            )
            token = data.get("token")
            if not token:
                raise ArtalkError("login response missing token", body=str(data))
            user = data.get("user") or {}
            if not user.get("is_admin"):
                raise ArtalkError("Artalk user is not admin")
            with self._lock:
                self._token = token
                self._token_exp = int(time.time()) + 86400
            return token

        user_id = lookup_admin_user_id(self.db_path, self.email, self.name)
        token = mint_admin_jwt(self.app_key, user_id)
        with self._lock:
            self._token = token
            self._token_exp = int(time.time()) + 86400 * 2
        return token

    def get_comment(self, comment_id: int) -> dict[str, Any]:
        data = self._request("GET", f"/api/v2/comments/{comment_id}", auth=True)
        comment = data.get("comment") if isinstance(data, dict) else None
        if not isinstance(comment, dict):
            raise ArtalkError(f"comment {comment_id} not found in response")
        return comment

    def update_comment(self, comment_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/api/v2/comments/{comment_id}", payload, auth=True)

    def delete_comment(self, comment_id: int) -> None:
        self._request("DELETE", f"/api/v2/comments/{comment_id}", auth=True)

    def delete_user(self, user_id: int) -> None:
        self._request("DELETE", f"/api/v2/users/{user_id}", auth=True)

    def find_admin_emails(self) -> set[str]:
        data = self._request("GET", "/api/v2/users/admin?limit=100&offset=0", auth=True)
        users = data.get("users") or []
        out: set[str] = set()
        for u in users:
            email = (u.get("email") or "").strip().lower()
            if email:
                out.add(email)
        return out
