import json
import urllib.request


def post(webhook_url: str, text: str, opener=urllib.request.urlopen) -> int:
    """Post a message to a Slack incoming webhook. `opener` is injectable for tests."""
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener(req, timeout=10) as resp:
        return resp.status
