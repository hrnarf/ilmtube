"""Write site data (SPEC §3.7) to site/public/data/. Shorts go to shorts.json only (not searched, not on shelves)."""
from __future__ import annotations
import re
from collections import Counter, defaultdict
import yaml
from .common import DATA, ROOT, load_yaml, read_json, write_json
from .surahs import SURAHS, variants

OUT = ROOT / "site" / "public" / "data"
PARENT_LABEL = {"quran": "Qur'an", "aqeedah": "Aqeedah (belief)", "seerah-history": "Seerah & history", "hadith": "Hadith", "fiqh": "Fiqh",
                "spirituality": "Spirituality", "character-family": "Character & family", "wellbeing": "Wellbeing", "contemporary": "Contemporary",
                "dawah": "Dawah", "seasons": "Seasons", "arabic": "Arabic"}
CHILD_LABEL = {"hifz": "Hifz (memorisation)", "heart": "The heart (tazkiyah)", "the-unseen": "The unseen (angels, jinn)", "akhlaq": "Akhlaq (manners)",
               "prophets": "Stories of the prophets", "quran-stories": "Qur'an stories", "explanations": "Hadith explanations", "zakat-charity": "Zakat & charity",
               "hajj-umrah": "Hajj & umrah", "halal-haram": "Halal & haram", "finance-business": "Finance & business", "marriage-divorce": "Marriage & divorce",
               "dua-dhikr": "Dua & dhikr", "patience-gratitude": "Patience & gratitude", "muharram-ashura": "Muharram & Ashura", "laylat-al-qadr": "Laylat al-Qadr",
               "dhul-hijjah": "Dhul Hijjah", "jumuah": "Jumu'ah", "science-and-islam": "Science & Islam", "muslims-in-the-west": "Muslims in the West",
               "grief-loss": "Grief & loss", "anxiety-stress": "Anxiety & stress", "hardship-trials": "Hardship & trials", "women-of-islam": "Women of Islam",
               "names-of-allah": "Names of Allah", "day-of-judgement": "Day of Judgement", "death-and-grave": "Death & the grave", "work-career": "Work & career",
               "parents-rights": "Parents' rights", "brotherhood-community": "Brotherhood & community", "marriage-relationships": "Marriage & relationships",
               "language-learning": "Language learning", "current-affairs": "Current affairs", "social-media": "Social media", "hadith-sciences": "Hadith sciences",
               "islamic-history": "Islamic history", "signs-of-the-hour": "Signs of the Hour", "prophet-muhammad": "The Prophet Muhammad ﷺ", "overcoming-sins": "Overcoming sins"}
SKIP_SERIES = {"uploads", "favorites", "favourites", "shorts"}


def label(slug: str) -> str:
    return CHILD_LABEL.get(slug, slug.replace("-", " ").capitalize())


def clean_desc(d: str) -> str:
    d = re.sub(r"https?://\S+", "", d)
    d = re.sub(r"\s+", " ", d).strip()
    return d[:280]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    clean = read_json(DATA / "videos_clean.json", [])
    rank = read_json(DATA / "rank.json", {})
    nmap = read_json(DATA / "name_map.json", {"speakers": {}, "reciters": {}})
    channels = [c for c in read_json(DATA / "channels.json", []) if c["status"] == "active"]
    cidx = {c["id"]: i for i, c in enumerate(channels)}
    tags = {}
    for v in clean:
        t = read_json(DATA / "tags" / f"{v['id']}.json")
        if t and not t["not_content"]:
            tags[v["id"]] = t
    kept = [v for v in clean if v["id"] in tags]
    dropped_nc = len(clean) - len(kept)

    # series (playlists with >=3 in-library videos)
    inlib = {v["id"] for v in kept if not v["is_short"]}
    series, vid_series = [], defaultdict(list)
    for ch in channels:
        pls = read_json(DATA / "raw" / ch["id"] / "playlists.json", {"playlists": {}})["playlists"]
        for pid, p in pls.items():
            if p["title"].strip().lower() in SKIP_SERIES or re.search(r"\bshorts?\b", p["title"], re.I):
                continue
            eps = [x for x in p["items"] if x in inlib]
            if len(eps) < 3:
                continue
            si = len(series)
            series.append({"id": pid, "t": p["title"], "c": cidx[ch["id"]], "v": eps})
            for n, x in enumerate(eps, 1):
                vid_series[x].append([si, n])

    sp_ids = lambda t: sorted({nmap["speakers"][s] for s in t["speakers"] if s in nmap["speakers"]})
    videos, shorts, descs = [], [], {}
    for v in kept:
        t, r = tags[v["id"]], rank.get(v["id"], {"q": 0})
        rec = {"id": v["id"], "c": cidx[v["channel_id"]], "t": v["title"], "p": v["published"][:10], "s": v["seconds"], "v": v["views"],
               "q": r["q"], "ty": t["content_type"], "tp": t["topics"], "sp": sp_ids(t), "su": t["surahs"], "au": t["audience"], "cf": t["confidence"]}
        rid = nmap["reciters"].get(t["reciter"]) if t["reciter"] else None
        if rid:
            rec["r"] = rid
        if v["is_short"]:
            shorts.append(rec)
        else:
            descs[v["id"]] = clean_desc(v["description"])
            rec["tr"] = r.get("trend", 0)
            rec["se"] = vid_series.get(v["id"], [])
            videos.append(rec)
    videos.sort(key=lambda x: x["p"], reverse=True)
    shorts.sort(key=lambda x: x["p"], reverse=True)

    # entities
    def entities(fname, key):
        ents = yaml.safe_load((ROOT / fname).read_text()) or []
        cnt, cnt_s, topics, surahs = Counter(), Counter(), defaultdict(Counter), defaultdict(set)
        for v in videos:
            for e in ([v.get("r")] if key == "r" and v.get("r") else v.get("sp", []) if key == "sp" else []):
                cnt[e] += 1
                topics[e].update(v["tp"])
                surahs[e].update(v["su"])
        for v in shorts:
            for e in ([v.get("r")] if key == "r" and v.get("r") else v.get("sp", []) if key == "sp" else []):
                cnt_s[e] += 1
        out = [{"id": e["id"], "name": e["name"], "aliases": e.get("aliases", []), "n": cnt[e["id"]], "ns": cnt_s[e["id"]],
                "tp": [t for t, _ in topics[e["id"]].most_common(5)], "su": sorted(surahs[e["id"]])} for e in ents]
        return sorted([x for x in out if x["n"] or x["ns"]], key=lambda x: -x["n"])

    tax = load_yaml("taxonomy.yaml")
    tcount = Counter(t for v in videos for t in v["tp"])
    topics = [{"id": p, "name": PARENT_LABEL[p], "n": sum(tcount[f"{p}.{c}"] for c in cs),
               "children": [{"id": f"{p}.{c}", "name": label(c), "n": tcount[f"{p}.{c}"]} for c in cs]} for p, cs in tax.items()]
    surah_count = Counter(s for v in videos for s in v["su"])
    surahs = [{"n": i + 1, "en": en, "ar": ar, "v": variants(i + 1), "count": surah_count[i + 1]} for i, (en, ar) in enumerate(SURAHS)]
    chans = [{"i": i, "id": c["id"], "t": c["title"], "handle": c["handle"], "thumb": c["thumbnail"], "subs": c["subscribers"],
              "n": sum(1 for v in videos if v["c"] == i), "ns": sum(1 for v in shorts if v["c"] == i)} for i, c in enumerate(channels)]

    # timeless: top quality per topic (any age), ids only
    timeless = {}
    for p, cs in tax.items():
        for c in cs:
            slug = f"{p}.{c}"
            top = sorted((v for v in videos if slug in v["tp"] and v["cf"] >= 0.6), key=lambda v: -v["q"])[:12]
            if top:
                timeless[slug] = [v["id"] for v in top]
    noteworthy = [v["id"] for v in sorted(videos, key=lambda v: -v["tr"])[:24]]

    write_json(OUT / "videos.json", videos)
    write_json(OUT / "shorts.json", shorts)
    write_json(OUT / "desc.json", descs)
    write_json(OUT / "channels.json", chans)
    write_json(OUT / "topics.json", topics)
    write_json(OUT / "speakers.json", entities("speakers.yaml", "sp"))
    write_json(OUT / "reciters.json", entities("reciters.yaml", "r"))
    write_json(OUT / "series.json", series)
    write_json(OUT / "surahs.json", surahs)
    write_json(OUT / "shelves.json", {"noteworthy": noteworthy, "timeless": timeless})
    write_json(OUT / "synonyms.json", load_yaml("synonyms.yaml"))
    print(f"videos {len(videos)}, shorts {len(shorts)}, not_content dropped {dropped_nc}, series {len(series)}, "
          f"speakers {len(entities('speakers.yaml','sp'))}, reciters {len(entities('reciters.yaml','r'))}")


if __name__ == "__main__":
    main()
