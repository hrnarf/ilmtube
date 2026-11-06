"""Rule-based exclusion (SPEC §3.3). Writes data/excluded.json (reasons) and data/videos_clean.json."""
from __future__ import annotations
import re
import httpx
from .common import DATA, config, read_json, write_json

_DUR = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def seconds(iso: str) -> int:
    d, h, m, s = (int(x or 0) for x in _DUR.match(iso or "PT0S").groups())
    return d * 86400 + h * 3600 + m * 60 + s


def is_short(vid: str, cache: dict, http: httpx.Client) -> bool | None:
    if vid in cache:
        return cache[vid]
    try:
        r = http.head(f"https://www.youtube.com/shorts/{vid}", follow_redirects=False)
    except httpx.HTTPError:
        return None
    if r.status_code not in (200, 303, 301, 302, 307, 308):
        return None
    cache[vid] = r.status_code == 200
    return cache[vid]


def main():
    cfg = config()
    limit = cfg.get("max_videos_per_channel")
    channels = [c for c in read_json(DATA / "channels.json", []) if c["status"] == "active"]
    cache = read_json(DATA / "shorts_cache.json", {})
    excluded, clean = {}, []
    http = httpx.Client(timeout=15)
    unverified_shorts = 0
    for ch in channels:
        d = DATA / "raw" / ch["id"]
        state, vids = read_json(d / "state.json"), read_json(d / "videos.json")
        held = state["ids"][:limit] if limit else state["ids"]
        for vid in held:
            v = vids.get(vid)
            if not v or v.get("_missing"):
                excluded[vid] = "unavailable (private or deleted)"
                continue
            sn, st, cd = v["snippet"], v.get("status", {}), v["contentDetails"]
            secs = seconds(cd.get("duration"))
            live = sn.get("liveBroadcastContent", "none")
            reason = None
            if live in ("upcoming", "live"):
                reason = f"live broadcast state: {live}"
            elif st.get("privacyStatus") != "public":
                reason = f"not public ({st.get('privacyStatus')})"
            elif st.get("embeddable") is False:
                reason = "not embeddable"
            elif secs < 60:
                reason = "duration < 60s (trailer/bumper)"
            elif secs <= 180 and not cfg.get("include_shorts", False):
                s = is_short(vid, cache, http)
                if s:
                    reason = "YouTube Short (<=180s, /shorts/ returned 200)"
                elif s is None:
                    unverified_shorts += 1  # could not verify: keep, tagger can flag not_content
            if reason:
                excluded[vid] = reason
                continue
            st_ = v.get("statistics", {})
            clean.append({
                "id": vid, "channel_id": ch["id"], "channel": ch["title"], "kind": ch["kind"],
                "single_speaker": ch.get("single_speaker"),
                "title": sn["title"], "description": sn.get("description", ""),
                "published": sn["publishedAt"], "seconds": secs,
                "views": int(st_.get("viewCount", 0)), "likes": int(st_.get("likeCount", 0)),
                "live": live,
            })
    write_json(DATA / "shorts_cache.json", cache)
    write_json(DATA / "excluded.json", excluded)
    write_json(DATA / "videos_clean.json", clean)
    from collections import Counter
    print(f"kept {len(clean)}, excluded {len(excluded)}; unverified-short candidates kept: {unverified_shorts}")
    for r, n in Counter(excluded.values()).most_common():
        print(f"  {n:4d}  {r}")


if __name__ == "__main__":
    main()
