"""Quality + trending scores (SPEC §3.6) -> data/rank.json {video_id: {q, trend}}.

quality = log1p(views) - median(log1p(views)) over the same channel's videos published in the same year
          (Shorts are bucketed separately), plus a small like/view-ratio boost (max +0.5).
trending = (quality + 2, floored at 0.05) * 0.5 ** (age_days / 30)   -- 30-day half-life; used only for "New & noteworthy".
"""
from __future__ import annotations
import math, statistics
from datetime import datetime, timezone
from .common import DATA, read_json, write_json


def main():
    vids = read_json(DATA / "videos_clean.json", [])
    now = datetime.now(timezone.utc)
    buckets: dict[tuple, list[float]] = {}
    chan: dict[tuple, list[float]] = {}
    for v in vids:
        y = v["published"][:4]
        buckets.setdefault((v["channel_id"], v["is_short"], y), []).append(math.log1p(v["views"]))
        chan.setdefault((v["channel_id"], v["is_short"]), []).append(math.log1p(v["views"]))
    out = {}
    for v in vids:
        b = buckets[(v["channel_id"], v["is_short"], v["published"][:4])]
        med = statistics.median(b if len(b) >= 5 else chan[(v["channel_id"], v["is_short"])])
        ratio = v["likes"] / v["views"] if v["views"] else 0
        q = math.log1p(v["views"]) - med + 10 * min(ratio, 0.05)
        age = max((now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).days, 0)
        out[v["id"]] = {"q": round(q, 3), "trend": round(max(q + 2, 0.05) * 0.5 ** (age / 30), 4)}
    write_json(DATA / "rank.json", out)
    print(f"ranked {len(out)} videos")


if __name__ == "__main__":
    main()
