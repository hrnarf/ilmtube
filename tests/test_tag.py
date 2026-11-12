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
