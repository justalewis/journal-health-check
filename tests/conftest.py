import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jhc.http import Response, build_url  # noqa: E402
from jhc.journals import Journal  # noqa: E402


class FakeHttp:
    """Answers from a dict of URL -> (status, body). Unlisted URLs 404.
    Keys may be exact full URLs or prefixes ending in '*'."""

    def __init__(self, routes: dict, final_urls: dict | None = None):
        self.routes = routes
        self.final_urls = final_urls or {}
        self.calls = []

    def _match(self, full):
        if full in self.routes:
            return self.routes[full]
        for k, v in self.routes.items():
            if k.endswith("*") and full.startswith(k[:-1]):
                return v
        return (404, "")

    def get(self, url, params=None, headers=None, allow_redirects=True, max_bytes=0):
        full = build_url(url, params)
        self.calls.append(full)
        status, body = self._match(full)
        if status is None:
            return Response(url=full, status=None, error="ConnectionError: boom")
        text = body if isinstance(body, str) else json.dumps(body)
        return Response(url=full, status=status, text=text,
                        final_url=self.final_urls.get(url, url))

    def get_json(self, url, params=None, **kw):
        r = self.get(url, params=params)
        data = None
        if r.ok:
            try:
                data = r.json()
            except ValueError:
                pass
        return r, data


def portal_page(issn, title, issn_l=None, keepers=None, status="Confirmed"):
    k = json.dumps(keepers or [])
    return f"""<html><head><title>ISSN {issn} - {title}</title>
<script>const recordKeepers = {k};</script></head><body>
<div>Displaying basic data</div><div>{status} record</div>
<div>Key title: {title}</div><div>Copy permalink</div>
<div>Identifiers ISSN: {issn} ISSN-L: {issn_l or issn}</div>
<div>Titles Title proper: {title}.</div><div>Publication Medium: Online</div>
<div>Record Last modified: 2025/01/02</div></body></html>"""


@pytest.fixture
def lics():
    return Journal(name="Literacy in Composition Studies", short="LiCS",
                   issn_online="2326-5620", home_url="https://licsjournal.org/",
                   platform="ojs", oa="gold")


@pytest.fixture
def fake():
    return FakeHttp
