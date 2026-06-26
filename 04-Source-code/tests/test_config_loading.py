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
    assert thresholds.datenqualitaet.min_plausible_dew_point_c == -50.0
    assert thresholds.plausibilitaet.min_temp_c == -50.0
    assert thresholds.plausibilitaet.max_temp_c == 50.0
    assert thresholds.plausibilitaet.min_humidity_pct == 0.0
    assert thresholds.plausibilitaet.max_humidity_pct == 100.0
    assert thresholds.plausibilitaet.min_pressure_hpa == 800.0
    assert thresholds.plausibilitaet.max_pressure_hpa == 1100.0


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


@pytest.mark.parametrize("gap", [0.0, 30.0, 59.0])
def test_max_continuity_gap_kleiner_als_on_delay_scheitert_laut(tmp_path, gap):
    # max_gap < on_delay -> jeder Poll bricht die Kontinuitaet, der On-Delay akkumuliert
    # nie -> es feuert NIE ein Alarm (Under-Alarm, NF-01-Verstoss). Muss laut scheitern.
    daten = _minimal_config()
    daten["hysterese"]["on_delay_s"] = 60.0
    daten["hysterese"]["max_continuity_gap_s"] = gap
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_max_continuity_gap_gleich_on_delay_ist_erlaubt(tmp_path):
    daten = _minimal_config()
    daten["hysterese"]["on_delay_s"] = 60.0
    daten["hysterese"]["max_continuity_gap_s"] = 60.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    thresholds = load_thresholds(datei)

    assert thresholds.hysterese.max_continuity_gap_s == 60.0


def test_unbekannter_schluessel_in_sektion_scheitert_laut(tmp_path):
    # NF-05: eine Safety-Config darf einen vertippten Key (z. B. 'off_delay_s' statt
    # 'on_delay_s') nicht still verwerfen -> der Operator glaubt sonst, eine Schwelle
    # geaendert zu haben, der Default bleibt aber aktiv. Spiegelt extra='forbid'.
    daten = _minimal_config()
    daten["hysterese"]["off_delay_s"] = 30.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize("ungueltig", [float("nan"), float("inf")])
def test_nicht_endliche_vereisungs_schwelle_scheitert_laut(tmp_path, ungueltig):
    # NaN/inf in einer Vereisungs-Schwelle wuerde in der Bewertung (DTB-38) alle
    # Vergleiche unterlaufen (NaN < x ist immer False -> fail-open). Muss laut scheitern.
    daten = _minimal_config()
    daten["vereisung"]["t_s_gefrierpunkt_c"] = ungueltig
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize("feld", ["on_delay_s", "max_continuity_gap_s", "downgrade_stable_s"])
def test_zu_grosse_zeitkonstante_scheitert_laut(feld):
    # Ein absurd grosser Wert wuerde entweder timedelta sprengen (OverflowError beim
    # Engine-Bau) oder den Alarm faktisch nie ausloesen (stiller Under-Alarm). Obergrenze
    # 24 h -> laut ConfigError statt verschleppter Crash / stiller Deaktivierung.
    from src.config.loader import HystereseParameter

    werte = {
        "on_delay_s": 60.0,
        "max_continuity_gap_s": 120.0,
        "downgrade_stable_s": 300.0,
        "downgrade_undershoot_c": 0.5,
    }
    werte[feld] = 1e18
    # max_gap muss >= on_delay bleiben, damit der Cross-Field-Check nicht zuerst greift.
    if feld == "on_delay_s":
        werte["max_continuity_gap_s"] = 1e18
    with pytest.raises(ConfigError):
        HystereseParameter(**werte)


def test_zeitkonstante_obergrenze_grenzfall():
    # Grenze _MAX_ZEIT_S = 86400 s (24 h): exakt erlaubt (`>`-Pruefung), knapp darueber nicht.
    from src.config.loader import HystereseParameter

    HystereseParameter(  # exakt 86400 -> ok
        on_delay_s=60.0,
        max_continuity_gap_s=86_400.0,
        downgrade_stable_s=86_400.0,
        downgrade_undershoot_c=0.5,
    )
    with pytest.raises(ConfigError):  # 86400.001 -> abgelehnt
        HystereseParameter(
            on_delay_s=60.0,
            max_continuity_gap_s=86_400.0,
            downgrade_stable_s=86_400.001,
            downgrade_undershoot_c=0.5,
        )


def test_undershoot_obergrenze_grenzfall():
    # Plausibilitaets-Grenze _MAX_UNDERSHOOT_C = 10 °C: exakt erlaubt, klar darueber abgelehnt.
    # Ein zu grosser Deadband wuerde eine Rueckstufung faktisch nie bestaetigen (NF-05-Geist:
    # Fehlkonfiguration frueh erkennen statt still die Stabilisierung deaktivieren).
    from src.config.loader import HystereseParameter

    HystereseParameter(  # exakt 10.0 -> ok
        on_delay_s=60.0,
        max_continuity_gap_s=120.0,
        downgrade_stable_s=300.0,
        downgrade_undershoot_c=10.0,
    )
    with pytest.raises(ConfigError):  # 50 °C -> abgelehnt (Fehlkonfiguration)
        HystereseParameter(
            on_delay_s=60.0,
            max_continuity_gap_s=120.0,
            downgrade_stable_s=300.0,
            downgrade_undershoot_c=50.0,
        )


def test_kommentar_key_in_sektion_wird_toleriert(tmp_path):
    # '_'-praefixierte Keys sind Kommentare und duerfen auch in einem Abschnitt stehen
    # (Konsistenz mit Top-Level). Echte Schwellen-Keys bleiben streng (Tippfehler-Test oben).
    daten = _minimal_config()
    daten["hysterese"]["_comment"] = "Inline-Hinweis fuer Operatoren"
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    thresholds = load_thresholds(datei)  # darf NICHT scheitern
    assert thresholds.hysterese.on_delay_s == 60.0


def test_default_config_laedt_poll_interval():
    # P0-a: die Poll-Kadenz des Schedulers ist parametrierbar (NF-05), nicht hardcodiert.
    thresholds = load_thresholds()
    assert thresholds.betrieb.poll_interval_s == 30.0


@pytest.mark.parametrize("ungueltig", [0.0, -1.0, float("nan"), float("inf")])
def test_ungueltiges_poll_interval_scheitert_laut(tmp_path, ungueltig):
    # poll_interval_s muss > 0 und endlich sein: 0/negativ wäre ein Dauerpoll bzw. sinnlos,
    # NaN/inf unterläuft jeden Vergleich. Laut scheitern statt still falsch konfigurieren.
    daten = _minimal_config()
    daten["betrieb"]["poll_interval_s"] = ungueltig
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


def test_poll_interval_groesser_als_max_gap_scheitert_laut(tmp_path):
    # Cross-Section (NF-01): pollt das System langsamer als die Kontinuitäts-Lücke der
    # Alarm-Hysterese, bricht jeder Poll die Eskalations-Kontinuität -> es feuert nie ein
    # Alarm (stiller Under-Alarm). Erst mit poll_interval_s in der Config erzwingbar.
    daten = _minimal_config()
    daten["betrieb"]["poll_interval_s"] = daten["hysterese"]["max_continuity_gap_s"] + 1.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize("ungueltig", [True, float("nan"), float("inf"), 0.0, -1.0, 86_401.0])
def test_betrieb_parameter_direktkonstruktion_validiert(ungueltig):
    # Direktkonstruktion (greift unabhängig vom Loader-Loop): bool/NaN/inf/<=0/zu-groß
    # werden laut abgelehnt; ein gültiger Wert konstruiert sauber.
    from src.config.loader import BetriebParameter

    BetriebParameter(poll_interval_s=30.0)  # gültig -> kein Fehler
    with pytest.raises(ConfigError):
        BetriebParameter(poll_interval_s=ungueltig)


def test_hysterese_parameter_lehnt_bool_bei_direktkonstruktion_ab():
    # bool ist int-Subtyp -> als Zeit/Marge nicht zulassen (Defense-in-Depth).
    from src.config.loader import HystereseParameter

    with pytest.raises(ConfigError):
        HystereseParameter(
            on_delay_s=True,  # noqa: FBT003
            max_continuity_gap_s=120.0,
            downgrade_stable_s=300.0,
            downgrade_undershoot_c=0.5,
        )


def test_hysterese_parameter_lehnt_nicht_endlich_bei_direktkonstruktion_ab():
    # Defense-in-Depth: auch bei direkter Konstruktion (nicht ueber den Loader) wird
    # NaN/inf abgewiesen -- __post_init__ schuetzt Aufrufer ausserhalb des Config-Pfads.
    from src.config.loader import HystereseParameter

    with pytest.raises(ConfigError):
        HystereseParameter(
            on_delay_s=float("nan"),
            max_continuity_gap_s=120.0,
            downgrade_stable_s=300.0,
            downgrade_undershoot_c=0.5,
        )


def test_on_delay_null_ist_erlaubt(tmp_path):
    # On-Delay 0 = bewusst kein Debounce (degeneriert, aber gueltig) -> kein Fehler.
    daten = _minimal_config()
    daten["hysterese"]["on_delay_s"] = 0.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    thresholds = load_thresholds(datei)

    assert thresholds.hysterese.on_delay_s == 0.0


def test_integer_schwellwert_wird_akzeptiert(tmp_path):
    # Ein JSON-Integer (z. B. 0 ohne Dezimalpunkt) ist ein gueltiger Schwellwert
    # (int wird neben float akzeptiert; nur bool/nicht-numerisch wird abgelehnt).
    daten = _minimal_config()
    daten["prognose"]["t_s_grenz_c"] = 0  # int, nicht 0.0
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    thresholds = load_thresholds(datei)

    assert thresholds.prognose.t_s_grenz_c == 0


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
        ("stale_timeout_s", 86_401),
        ("max_temp_jump_c_per_min", 0),
        ("max_temp_jump_c_per_min", -1),
        ("max_temp_jump_c_per_min", 100.1),
        ("flatline_timeout_min", 0),
        ("flatline_timeout_min", -1),
        ("flatline_timeout_min", 1_441),
        ("flatline_epsilon_c", -0.01),
        ("flatline_epsilon_c", 10.1),
        ("max_clock_skew_s", 0),
        ("max_clock_skew_s", -1),
        ("max_clock_skew_s", 3_601),
        ("min_plausible_dew_point_c", -100.1),
        ("min_plausible_dew_point_c", 50.1),
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


@pytest.mark.parametrize(
    "feld, wert",
    [
        ("min_temp_c", -100.1),
        ("min_temp_c", 100.1),
        ("max_temp_c", -100.1),
        ("max_temp_c", 100.1),
        ("min_humidity_pct", -0.01),
        ("min_humidity_pct", 100.1),
        ("max_humidity_pct", -0.01),
        ("max_humidity_pct", 100.1),
        ("min_pressure_hpa", 0),
        ("min_pressure_hpa", -1),
        ("min_pressure_hpa", 1800),
        ("min_pressure_hpa", 2000.1),
        ("max_pressure_hpa", 0),
        ("max_pressure_hpa", -1),
        # 1100.1/1800 liegen unter der frueheren 2000er-Grenze und waeren still
        # akzeptiert worden -> Regressionsnachweis fuer die 1100er-Grenze (DTB-93 LOW).
        ("max_pressure_hpa", 1100.1),
        ("max_pressure_hpa", 1800),
        ("max_pressure_hpa", 2000.1),
    ],
)
def test_plausibilitaet_grenzwert_unplausibel_scheitert_laut(tmp_path, feld: str, wert: float):
    # Arrange — Plausibilitaets-Grenzen muessen physikalisch sinnvoll sein (NF-01).
    daten = _minimal_config()
    daten["plausibilitaet"][feld] = wert
    datei = tmp_path / "thresholds.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_thresholds(datei)


@pytest.mark.parametrize(
    "min_feld, max_feld",
    [
        ("min_temp_c", "max_temp_c"),
        ("min_humidity_pct", "max_humidity_pct"),
        ("min_pressure_hpa", "max_pressure_hpa"),
    ],
)
def test_plausibilitaet_min_max_vertauscht_scheitert_laut(tmp_path, min_feld: str, max_feld: str):
    daten = _minimal_config()
    daten["plausibilitaet"][min_feld] = daten["plausibilitaet"][max_feld]
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
        "datenqualitaet": {
            "stale_timeout_s": 120,
            "max_temp_jump_c_per_min": 5.0,
            "flatline_timeout_min": 15.0,
            "flatline_epsilon_c": 0.01,
            "max_clock_skew_s": 5.0,
            "min_plausible_dew_point_c": -50.0,
        },
        "plausibilitaet": {
            "min_temp_c": -50.0,
            "max_temp_c": 50.0,
            "min_humidity_pct": 0.0,
            "max_humidity_pct": 100.0,
            "min_pressure_hpa": 800.0,
            "max_pressure_hpa": 1100.0,
        },
        "betrieb": {"poll_interval_s": 30.0},
    }
