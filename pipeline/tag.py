"""LLM tagging orchestration. The tagging itself is done by Claude Code subagents (no API).

  python -m pipeline.tag prepare   -> data/tag_queue/batch_NNN.jsonl (untagged/stale videos, ~150 each)
  (subagents read a batch + prompts/tag_v2.md, write data/tag_out/batch_NNN.jsonl)
  python -m pipeline.tag validate [model]  -> validates tag_out against schema + taxonomy, writes data/tags/<id>.json,
                                      re-queues failures (a fresh batch of only failed ids)
  python -m pipeline.tag second    -> queue low-confidence non-Shorts with playlist neighbour titles (SPEC §3.4 second pass)
  python -m pipeline.tag report    -> reports/low_confidence.md + reports/tagging_sample.md
"""
from __future__ import annotations
import hashlib, json, random, sys
from typing import Literal
from pydantic import BaseModel, Field, ValidationError, field_validator
from .common import DATA, ROOT, load_yaml, read_json, write_json, config

PROMPT_VERSION = "v2"
DEFAULT_MODEL = "claude-opus-5-5"  # recorded in each tag file; v2 tagging run by Opus 5.5, medium thinking
BATCH = 150
QUEUE, OUT, TAGS = DATA / "tag_queue", DATA / "tag_out" / PROMPT_VERSION, DATA / "tags"  # outputs kept per prompt version
ContentType = Literal["lecture", "reminder", "khutbah", "qa", "podcast", "debate", "recitation", "documentary", "kids", "nasheed", "news", "other"]
Audience = Literal["general", "youth", "sisters", "brothers", "reverts", "kids", "parents"]


def taxonomy_slugs() -> set[str]:
    return {f"{p}.{c}" for p, cs in load_yaml("taxonomy.yaml").items() for c in cs}


class Tag(BaseModel, extra="forbid"):
    id: str
    not_content: bool
    content_type: ContentType
    topics: list[str] = Field(min_length=1, max_length=3)
    speakers: list[str]
    reciter: str | None
    surahs: list[int]
    riwayah: str | None
    audience: list[Audience] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("topics")
    @classmethod
    def _topics(cls, v):
        bad = [t for t in v if t not in taxonomy_slugs()]
        if bad:
            raise ValueError(f"topics not in taxonomy: {bad}")
        return v

    @field_validator("surahs")
    @classmethod
    def _surahs(cls, v):
        if any(not 1 <= s <= 114 for s in v):
            raise ValueError("surah out of range 1-114")
        return v


def fingerprint(v: dict) -> str:
    return hashlib.sha1(f"{v['title']}\n{v['description'][:1500]}".encode()).hexdigest()[:12]


def playlist_titles() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    raw = DATA / "raw"
    for ch in raw.iterdir() if raw.exists() else []:
        pl = read_json(ch / "playlists.json", {"playlists": {}})["playlists"]
        for p in pl.values():
            for vid in p["items"]:
                out.setdefault(vid, []).append(p["title"])
    return out


def playlist_context(titles: dict[str, str], k: int = 2) -> dict[str, list[dict]]:
    """For each video: the playlists it's in, with the titles of the k videos before and after it."""
    out: dict[str, list[dict]] = {}
    raw = DATA / "raw"
    for ch in raw.iterdir() if raw.exists() else []:
        for p in read_json(ch / "playlists.json", {"playlists": {}})["playlists"].values():
            items = p["items"]
            for i, vid in enumerate(items):
                near = lambda xs: [titles[x] for x in xs if x in titles]
                out.setdefault(vid, []).append({"playlist": p["title"], "before": near(items[max(i - k, 0):i]), "after": near(items[i + 1:i + 1 + k])})
    return out


def low_confidence(tags: dict[str, dict], clean: dict[str, dict], cut: float = 0.6) -> list[dict]:
    """Low-confidence content videos worth a second look. Shorts and not_content are left out (owner decision)."""
    low = [t for t in tags.values() if t["confidence"] < cut and not t["not_content"] and not clean[t["id"]].get("is_short")]
    return sorted(low, key=lambda t: t["confidence"])


def needs_tag(v: dict) -> bool:
    t = read_json(TAGS / f"{v['id']}.json")
    return not t or t["prompt_version"] != PROMPT_VERSION or t["fingerprint"] != fingerprint(v)


def next_batch() -> int:
    """Next free batch number across the queue and this version's outputs."""
    return max([int(p.stem.split('_')[1]) for p in [*QUEUE.glob('batch_*.jsonl'), *OUT.glob('batch_*.jsonl')]] + [0]) + 1


def write_batches(vids: list[dict], start: int = 1) -> list:
    """Write ~BATCH-sized queue files starting at batch number `start`; return their paths."""
    pls = playlist_titles()
    QUEUE.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(0, len(vids), BATCH):
        path = QUEUE / f"batch_{start + len(paths):03d}.jsonl"
        paths.append(path)
        with open(path, "w") as f:
            for v in vids[i:i + BATCH]:
                f.write(json.dumps({
                    "id": v["id"], "title": v["title"], "description": v["description"][:1500],
                    "channel": v["channel"], "kind": v["kind"], "single_speaker_hint": v["single_speaker"],
                    "playlists": pls.get(v["id"], [])[:8], "seconds": v["seconds"], "is_short": v.get("is_short", False),
                }, ensure_ascii=False) + "\n")
    return paths


def prepare():
    clean = read_json(DATA / "videos_clean.json", [])
    todo = [v for v in clean if needs_tag(v)]
    for old in QUEUE.glob("batch_*.jsonl") if QUEUE.exists() else []:
        old.unlink()  # queue holds only pending work; finished raw outputs stay in tag_out/
    start = max([int(p.stem.split('_')[1]) for p in OUT.glob('batch_*.jsonl')] + [0]) + 1
    n = len(write_batches(todo, start))
    print(f"{len(todo)} videos to tag -> {n} batches in {QUEUE}")


def validate(model: str = DEFAULT_MODEL):
    """Validate every output line of this prompt version. For each video the LAST line (highest batch)
    wins. A tag file is only (re)written when its labels changed, so unchanged tags keep the model that
    made them. Videos whose latest line is invalid, or that have no tag yet, are re-queued."""
    clean = {v["id"]: v for v in read_json(DATA / "videos_clean.json", [])}
    TAGS.mkdir(parents=True, exist_ok=True)
    latest: dict[str, Tag | str] = {}          # id -> valid Tag, or error message
    for f in sorted(OUT.glob("batch_*.jsonl")):
        for ln, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                tag = Tag.model_validate_json(line)
                if tag.id not in clean:
                    raise ValueError("unknown video id")
                latest[tag.id] = tag
            except (ValidationError, ValueError) as e:
                try:
                    vid = json.loads(line).get("id")
                except Exception:
                    vid = None
                if vid in clean:
                    latest[vid] = f"{f.name}:{ln} " + str(e).splitlines()[0][:120]
                else:
                    print(f"  {f.name}:{ln} unparseable line")
    written = 0
    failed = {k: v for k, v in latest.items() if isinstance(v, str)}
    for vid, tag in latest.items():
        if isinstance(tag, str):
            continue
        new = {**tag.model_dump(), "prompt_version": PROMPT_VERSION, "fingerprint": fingerprint(clean[vid])}
        old = read_json(TAGS / f"{vid}.json")
        if old and {k: v for k, v in old.items() if k != "model"} == new:
            continue                            # unchanged: keep the model that produced it
        write_json(TAGS / f"{vid}.json", {**new, "model": model})
        written += 1
    missing = [v for v in clean.values() if v["id"] in failed or needs_tag(v)]
    print(f"valid: {len(latest) - len(failed)} ({written} written/changed); invalid latest line: {len(failed)}; to re-queue: {len(missing)}")
    for why in list(failed.values())[:10]:
        print(f"  {why}")
    if missing:
        nxt = next_batch()
        n = len(write_batches(missing, nxt))
        print(f"re-queued {len(missing)} videos in {n} new batch file(s) starting batch_{nxt:03d}")
    return len(missing)


def report():
    clean = {v["id"]: v for v in read_json(DATA / "videos_clean.json", [])}
    tags = {p.stem: read_json(p) for p in TAGS.glob("*.json")}
    tags = {k: t for k, t in tags.items() if k in clean}
    low = low_confidence(tags, clean)
    nc = [t for t in tags.values() if t["not_content"]]
    (ROOT / "reports").mkdir(exist_ok=True)
    with open(ROOT / "reports/low_confidence.md", "w") as f:
        f.write(f"# Low-confidence tags (<0.6, excluding Shorts and not_content): {len(low)}\n\n| id | conf | title | topics |\n|---|---|---|---|\n")
        for t in low:
            f.write(f"| {t['id']} | {t['confidence']:.2f} | {clean[t['id']]['title'].replace('|','/')} | {', '.join(t['topics'])} |\n")
    sample = random.Random(42).sample(sorted(tags), min(60, len(tags)))
    with open(ROOT / "reports/tagging_sample.md", "w") as f:
        f.write(f"# Tagging sample (60 random of {len(tags)}) for human spot-check\n\n| title | channel | topics | speakers | type | surahs | conf |\n|---|---|---|---|---|---|---|\n")
        for k in sample:
            t, v = tags[k], clean[k]
            f.write(f"| {v['title'].replace('|','/')} | {v['channel']} | {', '.join(t['topics'])} | {', '.join(t['speakers']) or '-'} | {t['content_type']}{' (NOT CONTENT)' if t['not_content'] else ''} | {', '.join(map(str,t['surahs'])) or '-'} | {t['confidence']:.2f} |\n")
    print(f"tagged {len(tags)}; low-confidence {len(low)}; not_content {len(nc)}")


def second():
    """Queue the second pass: low-confidence videos plus playlist neighbour titles, as one batch after the others."""
    clean = {v["id"]: v for v in read_json(DATA / "videos_clean.json", [])}
    tags = {p.stem: read_json(p) for p in TAGS.glob("*.json") if p.stem in clean}
    low = low_confidence(tags, clean)
    ctx = playlist_context({k: v["title"] for k, v in clean.items()})
    nxt = next_batch()
    paths = write_batches([clean[t["id"]] for t in low], nxt)
    n = len(paths)
    for f in paths:
        rows = [json.loads(x) for x in f.read_text().splitlines()]
        f.write_text("".join(json.dumps({**r, "second_pass": True, "first_pass": {k: tags[r["id"]][k] for k in ("content_type", "topics", "speakers", "confidence")}, "playlist_context": ctx.get(r["id"], [])}, ensure_ascii=False) + "\n" for r in rows))
    print(f"second pass: {len(low)} videos -> {n} batch(es) from batch_{nxt:03d}")


if __name__ == "__main__":
    {"prepare": prepare, "validate": validate, "report": report, "second": second}[sys.argv[1]](*sys.argv[2:])
