"""Polite HTTP for the harvester: one session, per-host spacing, retries, and
a file cache so a re-run in the same month doesn't hit anyone twice.

Nothing here raises on a network problem. A failed request comes back as a
Response with `status=None` and an `error`, and each check decides what that
means (almost always `unknown`, never `fail`: an unreachable API says nothing
about the journal).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

from . import config

# Seconds between requests to one host. Unlisted hosts get DEFAULT_SPACING.
HOST_SPACING = {
    "api.crossref.org": 0.25,
    "api.openalex.org": 0.2,
    "doaj.org": 0.6,
    "portal.issn.org": 1.5,
    "web.archive.org": 1.5,
    "archive.org": 1.5,
    "rdap.org": 0.5,
}
DEFAULT_SPACING = 1.0
RETRY_STATUSES = {429, 500, 502, 503, 504}
CACHE_TTL = 20 * 24 * 3600  # one harvest cycle, with slack


@dataclass
class Response:
    url: str                     # the URL asked for, params included
    status: int | None
    text: str = ""
    final_url: str | None = None
    headers: dict = field(default_factory=dict)
    error: str | None = None
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300

    @property
    def sha256(self) -> str | None:
        if self.status is None:
            return None
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def json(self):
        return json.loads(self.text)


def build_url(url: str, params: dict | None) -> str:
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urlencode(params, doseq=True)


class Http:
    def __init__(self, cache_dir: Path | None = None, use_cache: bool = True,
                 user_agent: str | None = None, timeout: float = 30.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent or config.USER_AGENT
        self.cache_dir = Path(cache_dir or config.CACHE_DIR)
        self.use_cache = use_cache
        self.timeout = timeout
        self._host_locks: dict[str, threading.Lock] = {}
        self._host_last: dict[str, float] = {}
        self._guard = threading.Lock()

    # -- spacing ----------------------------------------------------------

    def _wait_turn(self, host: str) -> threading.Lock:
        with self._guard:
            lock = self._host_locks.setdefault(host, threading.Lock())
        lock.acquire()
        gap = HOST_SPACING.get(host, DEFAULT_SPACING)
        elapsed = time.monotonic() - self._host_last.get(host, 0.0)
        if elapsed < gap:
            time.sleep(gap - elapsed)
        return lock

    # -- cache ------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / h[:2] / f"{h}.json"

    def _cache_get(self, key: str) -> Response | None:
        if not self.use_cache:
            return None
        p = self._cache_path(key)
        if not p.exists() or time.time() - p.stat().st_mtime > CACHE_TTL:
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return Response(from_cache=True, **d)

    def _cache_put(self, key: str, r: Response) -> None:
        # Only definite answers are cached. A 5xx or a timeout should be
        # retried on the next run, not remembered for three weeks.
        if r.status is None or r.status >= 500 or r.status == 429:
            return
        p = self._cache_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        d = {"url": r.url, "status": r.status, "text": r.text,
             "final_url": r.final_url, "headers": r.headers}
        p.write_text(json.dumps(d), encoding="utf-8")

    # -- requests ---------------------------------------------------------

    def get(self, url: str, params: dict | None = None,
            headers: dict | None = None, allow_redirects: bool = True,
            max_bytes: int = 3_000_000) -> Response:
        full = build_url(url, params)
        key = "GET " + full + (" noredirect" if not allow_redirects else "")
        cached = self._cache_get(key)
        if cached:
            return cached

        host = urlsplit(full).hostname or ""
        r = None
        for attempt in range(4):
            lock = self._wait_turn(host)
            try:
                raw = self.session.get(full, headers=headers, timeout=self.timeout,
                                       allow_redirects=allow_redirects, stream=True)
                body = raw.raw.read(max_bytes, decode_content=True) or b""
                raw.close()
                enc = raw.encoding or raw.apparent_encoding or "utf-8"
                r = Response(
                    url=full, status=raw.status_code,
                    text=body.decode(enc, errors="replace"),
                    final_url=raw.url,
                    headers={k.lower(): v for k, v in raw.headers.items()
                             if k.lower() in ("content-type", "last-modified",
                                              "location", "retry-after", "server")},
                )
            except requests.RequestException as exc:
                r = Response(url=full, status=None, error=f"{type(exc).__name__}: {exc}")
            finally:
                self._host_last[host] = time.monotonic()
                lock.release()

            if r.status in RETRY_STATUSES and attempt < 3:
                try:
                    wait = float(r.headers.get("retry-after", ""))
                except ValueError:
                    wait = 2 ** (attempt + 1)
                time.sleep(min(wait, 30))
                continue
            if r.status is None and attempt < 1:
                time.sleep(2)
                continue
            break

        self._cache_put(key, r)
        return r

    def get_json(self, url: str, params: dict | None = None, **kw):
        """(Response, parsed JSON or None)."""
        r = self.get(url, params=params, headers={"Accept": "application/json"}, **kw)
        data = None
        if r.ok:
            try:
                data = r.json()
            except ValueError:
                r.error = "response was not JSON"
        return r, data


_default: Http | None = None


def default_http() -> Http:
    global _default
    if _default is None:
        _default = Http()
    return _default
