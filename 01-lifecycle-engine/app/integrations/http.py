"""One tiny HTTP seam shared by the real integrations. Clients take a `transport` so tests can
run them with no network, and production uses urllib."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable

# (method, url, json_body, headers) -> (status_code, parsed_json_or_empty_dict)
Transport = Callable[[str, str, dict | None, dict], tuple[int, dict]]


def _parse(raw: bytes) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def urllib_transport(method: str, url: str, body: dict | None, headers: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, _parse(err.read())
