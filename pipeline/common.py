"""Shared helpers: paths, config, YouTube API client with quota counting."""
from __future__ import annotations
import json, os, time
from pathlib import Path
import httpx, yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
API = "https://www.googleapis.com/youtube/v3"


def load_yaml(name: str):
    return yaml.safe_load((ROOT / name).read_text())


def config() -> dict:
    return load_yaml("config.yaml")


def read_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True))


class YouTube:
    """Thin client. Each call costs 1 unit for list endpoints we use.

    In the cloud the proxy injects the key, so we send none. Only if
    YOUTUBE_API_KEY is set (GitHub Actions) do we send it, as a header.
    """

    def __init__(self):
        headers = {}
        if os.environ.get("YOUTUBE_API_KEY"):
            headers["X-Goog-Api-Key"] = os.environ["YOUTUBE_API_KEY"]
        self.http = httpx.Client(base_url=API, headers=headers, timeout=30)
        self.units = 0

    def get(self, endpoint: str, **params) -> dict:
        for attempt in range(4):
            r = self.http.get(f"/{endpoint}", params=params)
            if r.status_code in (500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            break
        if r.status_code >= 400:
            msg = r.json().get("error", {}).get("message", r.text[:200]) if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            raise RuntimeError(f"{endpoint} {r.status_code}: {msg}")
        self.units += 1
        return r.json()
