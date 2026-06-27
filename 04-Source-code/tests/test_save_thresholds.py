"""Tests fuer `save_thresholds()` (DTB-63, NF-05/NF-07).

Prueft atomisches Schreiben, Metadaten-Erhalt und Roundtrip-Laden.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.config.loader import ConfigError, load_thresholds, save_thresholds


def _full_config_with_metadata(metadata: dict) -> dict:
    base = load_thresholds()
    raw = asdict(base)
    raw.update(metadata)
    return raw


def test_save_thresholds_writes_all_sections(tmp_path: Path):
    thresholds = load_thresholds()
    path = tmp_path / "thresholds.json"

    save_thresholds(thresholds, path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["vereisung"]["t_s_gefrierpunkt_c"] == thresholds.vereisung.t_s_gefrierpunkt_c
    assert raw["hysterese"]["on_delay_s"] == thresholds.hysterese.on_delay_s
    assert raw["betrieb"]["poll_interval_s"] == thresholds.betrieb.poll_interval_s


def test_save_thresholds_preserves_top_level_metadata(tmp_path: Path):
    path = tmp_path / "thresholds.json"
    raw = _full_config_with_metadata({"_comment": "Hinweis", "_version": 3})
    path.write_text(json.dumps(raw), encoding="utf-8")
    thresholds = load_thresholds(path)

    save_thresholds(thresholds, path)

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["_comment"] == "Hinweis"
    assert reloaded["_version"] == 3


def test_save_thresholds_roundtrip(tmp_path: Path):
    original = load_thresholds()
    path = tmp_path / "thresholds.json"
    save_thresholds(original, path)

    reloaded = load_thresholds(path)

    assert reloaded == original


def test_save_thresholds_overwrites_sections_but_keeps_metadata(tmp_path: Path):
    path = tmp_path / "thresholds.json"
    thresholds = load_thresholds()
    save_thresholds(thresholds, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["_alt"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")

    save_thresholds(thresholds, path)

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert "vereisung" in reloaded
    assert reloaded["_alt"] is True


def test_save_thresholds_creates_missing_file(tmp_path: Path):
    path = tmp_path / "subdir" / "thresholds.json"
    thresholds = load_thresholds()

    save_thresholds(thresholds, path)

    assert path.exists()


def test_save_thresholds_rejects_invalid_json_target(tmp_path: Path):
    path = tmp_path / "thresholds.json"
    path.write_text("{ kein json", encoding="utf-8")
    thresholds = load_thresholds()

    with pytest.raises(ConfigError):
        save_thresholds(thresholds, path)


def test_save_thresholds_default_path_uses_loader_default(monkeypatch, tmp_path: Path):
    thresholds = load_thresholds()
    fake_default = tmp_path / "thresholds.json"
    monkeypatch.setattr("src.config.loader.DEFAULT_CONFIG_PATH", fake_default)

    save_thresholds(thresholds)

    assert fake_default.exists()
