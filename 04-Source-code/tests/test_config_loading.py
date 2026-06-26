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


def test_default_config_laedt_hysterese_parameter_aus_schwellenwerte_md():
    # Act
    thresholds = load_thresholds()

    # Assert — Entprellung/Hysterese gem. Schwellenwerte.md §2 (ISA-18.2):
    # On-Delay >= 60 s; Rueckstufung 0,5 C unterschritten und >= 5 min (300 s) stabil.
    assert thresholds.hysterese.on_delay_s == 60.0
    assert thresholds.hysterese.max_continuity_gap_s == 120.0
    assert thresholds.hysterese.downgrade_stable_s == 300.0
    assert thresholds.hysterese.downgrade_undershoot_c == 0.5


@pytest.mark.parametrize(
    "schluessel",
    ["on_delay_s", "max_continuity_gap_s", "downgrade_stable_s", "downgrade_undershoot_c"],
)
def test_negative_hysterese_konstante_scheitert_laut(tmp_path, schluessel):
    # Arrange — eine negative Zeit/Marge ist fachlich ungueltig und wuerde den
    # On-Delay-Debounce aushebeln (Sicherheitsparameter still ignoriert).
    daten = _minimal_config()
    daten["hysterese"][schluessel] = -1.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    # Act / Assert — Loader muss laut scheitern (kein stiller Default, NF-01-Geist).
    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize("ungueltig", [float("nan"), float("inf"), float("-inf")])
def test_nicht_endliche_hysterese_konstante_scheitert_laut(tmp_path, ungueltig):
    # NaN/inf wuerden alle >=-Vergleiche der Hysterese unterlaufen (NaN < 0 ist False!)
    # -> muessen laut abgewiesen werden, nicht still als verschleppter Crash auftauchen.
    daten = _minimal_config()
    daten["hysterese"]["on_delay_s"] = ungueltig
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_on_delay_null_ist_erlaubt(tmp_path):
    # On-Delay 0 = bewusst kein Debounce (degeneriert, aber gueltig) -> kein Fehler.
    daten = _minimal_config()
    daten["hysterese"]["on_delay_s"] = 0.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    thresholds = load_thresholds(datei)

    assert thresholds.hysterese.on_delay_s == 0.0


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
        "hysterese": {
            "on_delay_s": 60.0,
            "max_continuity_gap_s": 120.0,
            "downgrade_stable_s": 300.0,
            "downgrade_undershoot_c": 0.5,
        },
    }
