"""Speaker / reciter normalisation (SPEC §3.5).

  python -m pipeline.normalize names     -> data/raw_names.json (distinct raw names + counts) for the clustering subagent
  python -m pipeline.normalize apply     -> maps raw names to ids via speakers.yaml / reciters.yaml aliases;
                                            unmatched names -> reports/unmatched_names.md (never merged silently)

speakers.yaml / reciters.yaml are generated ONCE by a subagent from raw_names.json, then human-edited and authoritative.
"""
from __future__ import annotations
import re, sys
from collections import Counter
import yaml
from .common import DATA, ROOT, read_json, write_json

TITLES = r"\b(sheikh|shaykh|shaikh|imam|imaam|dr|ustadh|ustadha|ustaz|mufti|maulana|moulana|mawlana|prof|professor|hafiz|qari|qaari|br|brother|sr|sister)\b\.?"


def key(name: str) -> str:
    s = re.sub(TITLES, " ", name.lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", "").replace("’", ""))
    return " ".join(s.split())


def raw_names() -> tuple[Counter, Counter]:
    sp, re_ = Counter(), Counter()
    for p in (DATA / "tags").glob("*.json"):
        t = read_json(p)
        sp.update(t["speakers"])
        if t["reciter"]:
            re_[t["reciter"]] += 1
    return sp, re_


def names():
    sp, rc = raw_names()
    write_json(DATA / "raw_names.json", {"speakers": dict(sp.most_common()), "reciters": dict(rc.most_common())})
    print(f"{len(sp)} distinct speaker names, {len(rc)} distinct reciter names -> data/raw_names.json")


def index(fname: str) -> dict[str, str]:
    p = ROOT / fname
    entries = yaml.safe_load(p.read_text()) if p.exists() else []
    idx = {}
    for e in entries or []:
        for n in [e["name"], *e.get("aliases", [])]:
            idx[key(n)] = e["id"]
    return idx


def apply():
    sp, rc = raw_names()
    out, lines = {"speakers": {}, "reciters": {}}, []
    for label, counter, fname in (("speakers", sp, "speakers.yaml"), ("reciters", rc, "reciters.yaml")):
        idx = index(fname)
        unmatched = []
        for raw, n in counter.most_common():
            if key(raw) in idx:
                out[label][raw] = idx[key(raw)]
            else:
                unmatched.append((raw, n))
        lines.append(f"## {label} ({len(unmatched)} unmatched)\n")
        lines += [f"- {raw} ({n})" for raw, n in unmatched]
        lines.append("")
    write_json(DATA / "name_map.json", out)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/unmatched_names.md").write_text("# Unmatched names (add to speakers.yaml / reciters.yaml by hand)\n\n" + "\n".join(lines))
    print(f"mapped {len(out['speakers'])} speaker names, {len(out['reciters'])} reciter names; see reports/unmatched_names.md")


if __name__ == "__main__":
    {"names": names, "apply": apply}[sys.argv[1]]()
