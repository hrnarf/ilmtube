"""Incremental, quota-cheap fetch. Never uses search.list.

Per channel, data/raw/<channel_id>/:
  state.json     ordered video ids (newest first), backfill cursor, timestamps
  videos.json    video_id -> enriched resource (snippet, contentDetails, statistics, status, liveStreamingDetails)
  playlists.json {playlists: {id: {title, items:[video_id,...]}}, fetched_at}

Respects config max_videos_per_channel: head phase fetches new uploads until a
known id appears; tail phase continues backfill only while we hold fewer than max.
"""
from __future__ import annotations
import time
from .common import DATA, YouTube, config, read_json, write_json

WEEK = 7 * 86400
VPART = "snippet,contentDetails,statistics,status,liveStreamingDetails"


def chunks(xs, n=50):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def page(yt, pl, token):
    p = {"pageToken": token} if token else {}
    r = yt.get("playlistItems", part="contentDetails", playlistId=pl, maxResults=50, **p)
    return [i["contentDetails"]["videoId"] for i in r.get("items", [])], r.get("nextPageToken")


def fetch_uploads(yt, pl, state, limit):
    """state['ids'] is every id listed so far, newest first (may exceed limit by <50)."""
    ids = state["ids"]
    known = set(ids)
    first_run = not ids
    new, token = [], None
    # Head: new uploads, stop at the first known id.
    while True:
        vids, token = page(yt, pl, token)
        hit = False
        for v in vids:
            if v in known:
                hit = True
                break
            if v not in new:
                new.append(v)
        if hit or not token or (first_run and limit and len(new) >= limit):
            break
    if first_run:
        state["cursor"], state["complete"] = token, not token
    state["ids"] = ids = new + ids
    # Tail: only while we hold fewer than the cap (raising the cap is incremental).
    while (limit is None or len(ids) < limit) and state.get("cursor") and not state["complete"]:
        vids, state["cursor"] = page(yt, pl, state["cursor"])
        ids += [v for v in vids if v not in set(ids)]
        state["complete"] = not state["cursor"]
    return len(new)


def enrich(yt, vids, ids):
    for batch in chunks(ids):
        r = yt.get("videos", part=VPART, id=",".join(batch), maxResults=50)
        got = {it["id"]: it for it in r.get("items", [])}
        for i in batch:
            if i in got:
                vids[i] = {**got[i], "_fetched_at": int(time.time())}
            else:  # private/deleted: record so we stop retrying and clean.py can drop it
                vids[i] = {"id": i, "_missing": True, "_fetched_at": int(time.time())}


def fetch_playlists(yt, cid, uploads_pl):
    pls = {}
    token = None
    while True:
        r = yt.get("playlists", part="snippet,contentDetails", channelId=cid, maxResults=50, **({"pageToken": token} if token else {}))
        for p in r.get("items", []):
            if p["id"] != uploads_pl:
                pls[p["id"]] = {"title": p["snippet"]["title"], "count": p["contentDetails"]["itemCount"], "items": []}
        token = r.get("nextPageToken")
        if not token:
            break
    for pid, p in pls.items():
        if p["count"] < 3:
            continue  # spec: skip tiny playlists
        token = None
        while True:
            r = yt.get("playlistItems", part="contentDetails", playlistId=pid, maxResults=50, **({"pageToken": token} if token else {}))
            p["items"] += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
            token = r.get("nextPageToken")
            if not token:
                break
    return {"playlists": pls, "fetched_at": int(time.time())}


def main():
    cfg = config()
    limit = cfg.get("max_videos_per_channel")
    channels = [c for c in read_json(DATA / "channels.json", []) if c["status"] == "active"]
    yt = YouTube()
    now = int(time.time())
    for ch in channels:
        d = DATA / "raw" / ch["id"]
        state = read_json(d / "state.json", {"ids": [], "cursor": None, "complete": False})
        vids = read_json(d / "videos.json", {})
        n_new = fetch_uploads(yt, ch["uploads_playlist"], state, limit)
        held = state["ids"][:limit] if limit else state["ids"]  # never enrich beyond the cap
        todo = [i for i in held if i not in vids]
        enrich(yt, vids, todo)
        # weekly stats refresh of everything held
        if now - state.get("stats_refreshed_at", 0) > WEEK:
            stale = [i for i in held if i not in todo]
            enrich(yt, vids, stale)
            state["stats_refreshed_at"] = now
        pl = read_json(d / "playlists.json")
        if not pl or now - pl["fetched_at"] > WEEK:
            write_json(d / "playlists.json", fetch_playlists(yt, ch["id"], ch["uploads_playlist"]))
        state["updated_at"] = now
        write_json(d / "state.json", state)
        write_json(d / "videos.json", vids)
        missing = sum(1 for i in held if vids.get(i, {}).get("_missing"))
        print(f"{ch['title']}: held={len(held)} new={n_new} enriched={len(todo)} unavailable={missing} (channel reports {ch['video_count']})")
    print(f"units used: {yt.units}")


if __name__ == "__main__":
    main()
