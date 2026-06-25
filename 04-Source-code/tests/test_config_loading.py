"""Tests für den Threshold-Config-Loader (DTB-15, NF-05).

Belegt das Verhalten des Config-Enablers für DTB-38:
- Default-Config wird geladen; Startwerte stammen aus Schwellenwerte.md §2 (Kaskade).
- Eigener Pfad ist parametrierbar (NF-05: Schwellen zur Laufzeit ohne Recompile austauschbar).
- Ungültige/fehlende Config scheitert *laut* (ConfigError) statt stiller Defaults — Fail-safe-Geist.
"""

import json
from pathlib import Path

import pytest

from src.config.loader import ConfigError, Thresholds, load_thresholds


def test_default_config_laedt_kaskaden_schwellen_aus_schwellenwerte_md():
    # Act
    thresholds = load_thresholds()

    # Assert — Startwerte gem. Schwellenwerte.md §2 (priorisierte Kaskade)
    assert isinstance(thresholds, Thresholds)
    assert thresholds.vereisung.t_s_gefrierpunkt_c == 0.0
    assert thresholds.vereisung.t_s_gelb_auffang_c == 1.0
    assert thresholds.vereisung.delta_t_kondensation_k == 0.0
    assert thresholds.vereisung.delta_t_feucht_k == 1.0
    assert thresholds.prognose.t_s_grenz_c == 0.0
    assert thresholds.datenqualitaet.stale_timeout_s == 120.0
    assert thresholds.datenqualitaet.max_temp_jump_c_per_min == 5.0
    assert thresholds.datenqualitaet.flatline_timeout_min == 15.0
    assert thresholds.datenqualitaet.flatline_epsilon_c == 0.01
    assert thresholds.datenqualitaet.max_clock_skew_s == 5.0


def test_eigener_pfad_ist_parametrierbar(tmp_path):
    # Arrange — NF-05: Schwellen über externe Config austauschbar
    eigene = tmp_path / "thresholds.json"
    eigene.write_text(json.dumps(_minimal_config(t_s_gefrierpunkt=-1.5)), encoding="utf-8")

    # Act
    thresholds = load_thresholds(eigene)

    # Assert
    assert thresholds.vereisung.t_s_gefrierpunkt_c == -1.5


def test_pfad_als_string_funktioniert(tmp_path):
    # Arrange — Signatur erlaubt Path | str; hier wird ein str-Pfad übergeben
    eigene = tmp_path / "thresholds.json"
    eigene.write_text(json.dumps(_minimal_config(t_s_gefrierpunkt=-2.0)), encoding="utf-8")

    # Act
    thresholds = load_thresholds(str(eigene))

    # Assert
    assert thresholds.vereisung.t_s_gefrierpunkt_c == -2.0


def test_fehlende_datei_scheitert_laut():
    with pytest.raises(ConfigError):
        load_thresholds(Path("gibtsnicht/thresholds.json"))


def test_ungueltiges_json_scheitert_laut(tmp_path):
    kaputt = tmp_path / "thresholds.json"
    kaputt.write_text("{ kein valides json ", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(kaputt)


def test_fehlender_pflichtabschnitt_scheitert_laut(tmp_path):
    daten = _minimal_config()
    del daten["prognose"]
    unvollstaendig = tmp_path / "thresholds.json"
    unvollstaendig.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(unvollstaendig)


def test_fehlender_pflichtschluessel_scheitert_laut(tmp_path):
    daten = _minimal_config()
    del daten["vereisung"]["delta_t_feucht_k"]
    unvollstaendig = tmp_path / "thresholds.json"
    unvollstaendig.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(unvollstaendig)


def test_nicht_objekt_json_scheitert_laut(tmp_path):
    # Arrange — gültiges JSON, aber kein Objekt (z. B. nur eine Zahl)
    datei = tmp_path / "thresholds.json"
    datei.write_text("42", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_abschnitt_kein_objekt_scheitert_laut(tmp_path):
    daten = _minimal_config()
    daten["vereisung"] = 5  # Abschnitt ist kein JSON-Objekt
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_nicht_numerischer_schwellwert_scheitert_laut(tmp_path):
    # Arrange — String statt Zahl (z. B. deutsche Komma-Schreibweise "0,0")
    daten = _minimal_config()
    daten["vereisung"]["t_s_gefrierpunkt_c"] = "0,0"
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_boolescher_schwellwert_scheitert_laut(tmp_path):
    # Arrange — bool ist in Python ein int-Subtyp, aber keine gültige Schwelle
    daten = _minimal_config()
    daten["vereisung"]["t_s_gefrierpunkt_c"] = True
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize(
    "feld, wert",
    [
        ("stale_timeout_s", 0),
        ("stale_timeout_s", -1),
        ("max_temp_jump_c_per_min", 0),
        ("max_temp_jump_c_per_min", -1),
        ("flatline_timeout_min", 0),
        ("flatline_timeout_min", -1),
        ("flatline_epsilon_c", -0.01),
        ("max_clock_skew_s", 0),
        ("max_clock_skew_s", -1),
    ],
)
def test_datenqualitaet_grenzwert_unplausibel_scheitert_laut(tmp_path, feld: str, wert: float):
    # Arrange — DTB-13: Fail-safe-Grenzwerte muessen positiv (bzw. nicht negativ) sein
    daten = _minimal_config()
    daten["datenqualitaet"][feld] = wert
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def _minimal_config(t_s_gefrierpunkt: float = 0.0) -> dict:
    """Vollständige, valide Minimal-Config für die Negativ-/Parametrier-Tests."""
    return {
        "vereisung": {
            "t_s_gefrierpunkt_c": t_s_gefrierpunkt,
            "t_s_gelb_auffang_c": 1.0,
            "delta_t_kondensation_k": 0.0,
            "delta_t_feucht_k": 1.0,
        },
        "prognose": {"t_s_grenz_c": 0.0},
        "datenqualitaet": {
            "stale_timeout_s": 120,
            "max_temp_jump_c_per_min": 5.0,
            "flatline_timeout_min": 15.0,
            "flatline_epsilon_c": 0.01,
            "max_clock_skew_s": 5.0,
        },
    }
