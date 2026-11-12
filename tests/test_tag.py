"""Tests for pipeline/tag.py: schema, taxonomy, prompt versioning, model recording."""
import json
import pytest
from pipeline import tag

BASE = {"id": "abc", "not_content": False, "content_type": "reminder", "topics": ["fiqh.salah"],
        "speakers": [], "reciter": None, "surahs": [], "riwayah": None, "audience": ["general"], "confidence": 0.8}


def test_accepts_valid_tag():
    assert tag.Tag.model_validate(BASE).topics == ["fiqh.salah"]


def test_rejects_topic_outside_taxonomy():
    with pytest.raises(ValueError):
        tag.Tag.model_validate({**BASE, "topics": ["made.up"]})


def test_rejects_surah_out_of_range():
    with pytest.raises(ValueError):
        tag.Tag.model_validate({**BASE, "surahs": [115]})


def test_news_content_type_allowed():
    assert tag.Tag.model_validate({**BASE, "content_type": "news"}).content_type == "news"


def test_politics_topic_in_taxonomy():
    assert "contemporary.politics" in tag.taxonomy_slugs()


def test_prompt_version_is_v2_and_prompt_file_exists():
    assert tag.PROMPT_VERSION == "v2"
    assert (tag.ROOT / "pipeline/prompts/tag_v2.md").exists()


@pytest.fixture
def tmp_tags(tmp_path, monkeypatch):
    monkeypatch.setattr(tag, "TAGS", tmp_path)
    return tmp_path


VID = {"id": "abc", "title": "T", "description": "D"}


def test_needs_tag_when_prompt_version_is_old(tmp_tags):
    (tmp_tags / "abc.json").write_text(json.dumps({"prompt_version": "v1", "fingerprint": tag.fingerprint(VID)}))
    assert tag.needs_tag(VID)


def test_no_retag_when_current(tmp_tags):
    (tmp_tags / "abc.json").write_text(json.dumps({"prompt_version": tag.PROMPT_VERSION, "fingerprint": tag.fingerprint(VID)}))
    assert not tag.needs_tag(VID)


def test_validate_records_model(tmp_path, monkeypatch):
    out, tags = tmp_path / "out", tmp_path / "tags"
    out.mkdir()
    monkeypatch.setattr(tag, "OUT", out)
    monkeypatch.setattr(tag, "TAGS", tags)
    monkeypatch.setattr(tag, "QUEUE", tmp_path / "queue")
    monkeypatch.setattr(tag, "read_json", lambda p, d=None: [VID] if p.name == "videos_clean.json" else (json.loads(p.read_text()) if p.exists() else d))
    monkeypatch.setattr(tag, "playlist_titles", lambda: {})
    (out / "batch_001.jsonl").write_text(json.dumps(BASE) + "\n")
    tag.validate(model="claude-opus-5-5")
    assert json.loads((tags / "abc.json").read_text())["model"] == "claude-opus-5-5"


def test_playlist_titles_tolerates_missing_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(tag, "DATA", tmp_path)
    assert tag.playlist_titles() == {}


def test_outputs_are_kept_per_prompt_version():
    assert tag.OUT.name == tag.PROMPT_VERSION


def test_low_confidence_excludes_shorts_and_not_content():
    clean = {"a": {"is_short": False}, "b": {"is_short": True}, "c": {"is_short": False}, "d": {"is_short": False}}
    tags = {"a": {"id": "a", "confidence": 0.4, "not_content": False},
            "b": {"id": "b", "confidence": 0.3, "not_content": False},   # Short: excluded
            "c": {"id": "c", "confidence": 0.2, "not_content": True},    # ad: excluded
            "d": {"id": "d", "confidence": 0.9, "not_content": False}}   # confident
    assert [t["id"] for t in tag.low_confidence(tags, clean)] == ["a"]


def test_playlist_context_gives_neighbouring_titles(tmp_path, monkeypatch):
    ch = tmp_path / "raw" / "UC1"
    ch.mkdir(parents=True)
    (ch / "playlists.json").write_text(json.dumps({"playlists": {"PL1": {"title": "Ramadan 2026", "items": ["v1", "v2", "v3", "v4", "v5", "v6"]}}}))
    monkeypatch.setattr(tag, "DATA", tmp_path)
    titles = {f"v{i}": f"T{i}" for i in range(1, 7)}
    ctx = tag.playlist_context(titles)
    assert ctx["v4"] == [{"playlist": "Ramadan 2026", "before": ["T2", "T3"], "after": ["T5", "T6"]}]
    assert ctx["v1"][0]["before"] == []
