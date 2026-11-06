"""Resolve channels.yaml entries to channel IDs + uploads playlists -> data/channels.json."""
from __future__ import annotations
from .common import DATA, YouTube, load_yaml, write_json

PART = "snippet,contentDetails,statistics"


def main():
    yt = YouTube()
    out = []
    for ch in load_yaml("channels.yaml"):
        params = {"forHandle": ch["handle"]} if "handle" in ch else {"id": ch["id"]}
        items = yt.get("channels", part=PART, **params).get("items", [])
        if not items:
            raise SystemExit(f"Could not resolve {ch}")
        it = items[0]
        rec = {
            "id": it["id"],
            "handle": ch.get("handle") or it["snippet"].get("customUrl"),
            "title": it["snippet"]["title"],
            "thumbnail": it["snippet"]["thumbnails"].get("medium", {}).get("url"),
            "subscribers": int(it["statistics"].get("subscriberCount", 0)),
            "video_count": int(it["statistics"].get("videoCount", 0)),
            "uploads_playlist": it["contentDetails"]["relatedPlaylists"]["uploads"],
            "kind": ch["kind"],
            "single_speaker": ch.get("single_speaker"),
            "status": ch["status"],
        }
        out.append(rec)
        print(f"{rec['id']}  {rec['title']!r}  subs={rec['subscribers']:,}  videos={rec['video_count']:,}  ({rec['handle']})")
    write_json(DATA / "channels.json", out)
    print(f"units used: {yt.units}")


if __name__ == "__main__":
    main()
