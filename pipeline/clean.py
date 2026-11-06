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
    from concurrent.futures import ThreadPoolExecutor
    cfg = config()
    limit = cfg.get("max_videos_per_channel")
    include_shorts = cfg.get("include_shorts", False)
    channels = [c for c in read_json(DATA / "channels.json", []) if c["status"] == "active"]
    cache = read_json(DATA / "shorts_cache.json", {})
    http = httpx.Client(timeout=15)
    rows = []  # (channel, id, resource)
    for ch in channels:
        d = DATA / "raw" / ch["id"]
        state, vids = read_json(d / "state.json"), read_json(d / "videos.json")
        held = state["ids"][:limit] if limit else state["ids"]
        rows += [(ch, vid, vids.get(vid)) for vid in held]
    # Shorts check (SPEC §3.3) for every candidate <=180s that is otherwise public, in parallel.
    cand = [vid for _, vid, v in rows if v and not v.get("_missing") and seconds(v["contentDetails"].get("duration")) <= 180 and vid not in cache]
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda i: is_short(i, cache, http), cand))
    excluded, clean = {}, []
    unverified = 0
    for ch, vid, v in rows:
        if not v or v.get("_missing"):
            excluded[vid] = "unavailable (private or deleted)"
            continue
        sn, st, cd = v["snippet"], v.get("status", {}), v["contentDetails"]
        secs = seconds(cd.get("duration"))
        live = sn.get("liveBroadcastContent", "none")
        short = False
        reason = None
        if live in ("upcoming", "live"):
            reason = f"live broadcast state: {live}"
        elif st.get("privacyStatus") != "public":
            reason = f"not public ({st.get('privacyStatus')})"
        elif st.get("embeddable") is False:
            reason = "not embeddable"
        elif secs <= 180:
            s = cache.get(vid)
            if s:
                short = True
                if not include_shorts:
                    reason = "YouTube Short (<=180s, /shorts/ returned 200)"
            elif secs < 60:
                reason = "duration < 60s, not a Short (trailer/bumper)"
            elif s is None:
                unverified += 1  # could not verify: keep, tagger can flag not_content
        if reason:
            excluded[vid] = reason
            continue
        st_ = v.get("statistics", {})
        clean.append({
            "id": vid, "channel_id": ch["id"], "channel": ch["title"], "kind": ch["kind"],
            "single_speaker": ch.get("single_speaker"), "is_short": short,
            "title": sn["title"], "description": sn.get("description", ""),
            "published": sn["publishedAt"], "seconds": secs,
            "views": int(st_.get("viewCount", 0)), "likes": int(st_.get("likeCount", 0)),
            "live": live,
        })
    write_json(DATA / "shorts_cache.json", cache)
    write_json(DATA / "excluded.json", excluded)
    write_json(DATA / "videos_clean.json", clean)
    from collections import Counter
    print(f"kept {len(clean)} ({sum(v['is_short'] for v in clean)} Shorts), excluded {len(excluded)}; unverified-short candidates kept: {unverified}")
    for r, n in Counter(excluded.values()).most_common():
        print(f"  {n:4d}  {r}")


if __name__ == "__main__":
    main()
