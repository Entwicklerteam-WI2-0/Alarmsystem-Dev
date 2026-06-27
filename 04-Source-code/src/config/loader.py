"""Loader für die parametrierbaren Schwellenwerte (DTB-15, NF-05).

Liest die Schwellen aus einer JSON-Config (Default `config/thresholds.json` oder ein
eigener Pfad) und gibt ein validiertes, unveränderliches `Thresholds`-Objekt zurück.
Enabler für das Bewertungsmodul DTB-38. DB-frei (NF-05; DB-Secrets gehören NICHT hierher).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_type_hints

# config/thresholds.json liegt zwei Ebenen über src/config/loader.py
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds.json"


class ConfigError(Exception):
    """Konfiguration fehlt oder ist ungültig — bewusst lautes Scheitern statt stiller Defaults."""


# Obergrenze für Hysterese-Zeitkonstanten (Sekunden). Ein absurd großer Wert würde sonst
# entweder `timedelta` sprengen (OverflowError beim Engine-Bau) oder den Alarm faktisch nie
# auslösen (stiller Under-Alarm). 24 h ist für jede Vereisungs-Entprellung mehr als genug.
_MAX_ZEIT_S = 86_400.0

# Plausibilitäts-Obergrenze für die Rückstufungs-Marge (°C/K). Ein zu großer Deadband würde
# eine Rückstufung faktisch nie bestätigen (Anzeige bliebe dauerhaft auf der höheren Stufe).
# Generös bemessen, fängt Tippfehler ab (NF-05-Geist); der reale G1-Wert liegt weit darunter.
_MAX_UNDERSHOOT_C = 10.0

# Plausibler Bereich für eine Oberflächentemperatur-Schwelle (°C). Generös bemessen
# (NF-05: finale Werte von G1), fängt aber grobe Fehlkonfigurationen ab, die die Prognose-
# Vorwarnung still abschalten würden (FA-06).
_MIN_PLAUSIBLE_SURFACE_TEMP_C = -50.0
_MAX_PLAUSIBLE_SURFACE_TEMP_C = 50.0


@dataclass(frozen=True)
class VereisungsSchwellen:
    t_s_gefrierpunkt_c: float
    t_s_gelb_auffang_c: float
    delta_t_kondensation_k: float
    delta_t_feucht_k: float


@dataclass(frozen=True)
class PrognoseSchwellen:
    t_s_grenz_c: float
    # DTB-33 (FA-06): Parameter der 30-min-Trendextrapolation (NF-05, parametrierbar).
    trend_window_min: float  # Laenge des Trendfensters in Minuten
    horizon_min: float  # Prognosehorizont in Minuten (FA-06: 30)
    min_points: int  # Mindestanzahl Stuetzstellen fuer eine Regression (>= 2)
    max_readings_limit: int  # Obergrenze fuer gelesene Historien-Readings (DB-Last)


@dataclass(frozen=True)
class HystereseParameter:
    """Entprellung/Hysterese der Alarm-Generierung (DTB-27, Schwellenwerte.md §2).

    Zeitkonstanten in Sekunden, Temperatur-Marge in °C. Gegen Chattering (ISA-18.2):
    Hochstufung (Auslösen) erst nach `on_delay_s` anhaltender Bedingung — von der
    Engine umgesetzt. `max_continuity_gap_s` begrenzt, wie lange eine Unsicherheits-
    /Stale-Phase (UNKNOWN) die laufende Eskalation einfrieren darf, ohne die Kontinuität
    zu brechen (Default = Stale-Timeout 120 s); danach ist ein frischer On-Delay nötig.
    Invariante: `max_continuity_gap_s >= on_delay_s` (erzwungen) UND
    `>= betrieb.poll_interval_s` (seit P0-a in der Config -> querschnittlich von `Thresholds`
    erzwungen) — sonst bricht jeder Poll die Kontinuität und es feuert nie ein Alarm.
    Die Rückstufung (`downgrade_undershoot_c` um 0,5 °C unterschritten UND
    `downgrade_stable_s` stabil) gehört NICHT zum Alarm-On-Delay: sie ist eine
    temperaturgekoppelte **Anzeige-Hysterese** (Stabilisierung der gemeldeten Risikostufe
    für die Ampel) — umgesetzt in `src/alarm/riskhysterese.py` (`RiskHysterese`, Konsument
    DTB-43). Damit hat JEDE Hysterese-Zeitkonstante genau einen Wohnort. KEIN Auto-Clear (RB-01).
    """

    on_delay_s: float
    max_continuity_gap_s: float
    downgrade_stable_s: float  # Rückstufungs-Stabilität -> RiskHysterese (Anzeige)
    downgrade_undershoot_c: float  # Rückstufungs-Deadband -> RiskHysterese (Anzeige)

    def __post_init__(self) -> None:
        # Ungültige Werte würden den Debounce aushebeln (Sicherheitsparameter still
        # ignoriert) -> laut scheitern statt klaglos laden. NaN/inf sind besonders
        # tückisch: `nan < 0` ist False, also separat über isfinite abfangen.
        for feld, wert in (
            ("on_delay_s", self.on_delay_s),
            ("max_continuity_gap_s", self.max_continuity_gap_s),
            ("downgrade_stable_s", self.downgrade_stable_s),
            ("downgrade_undershoot_c", self.downgrade_undershoot_c),
        ):
            # bool ist ein int-Subtyp -- als Zeit/Marge nicht zulassen (Defense-in-Depth
            # zum Loader, der bool ebenfalls ablehnt; greift bei direkter Konstruktion).
            if isinstance(wert, bool):
                raise ConfigError(
                    f"Hysterese-Parameter '{feld}' darf kein bool sein, ist aber {wert!r}"
                )
            if not math.isfinite(wert):
                raise ConfigError(
                    f"Hysterese-Parameter '{feld}' muss endlich sein, ist aber {wert!r}"
                )
            if wert < 0:
                raise ConfigError(f"Hysterese-Parameter '{feld}' muss >= 0 sein, ist aber {wert!r}")
        # Obergrenze für die Zeitkonstanten (Sekunden): absurd große Werte sprengen timedelta
        # oder deaktivieren den Alarm faktisch.
        for feld, wert in (
            ("on_delay_s", self.on_delay_s),
            ("max_continuity_gap_s", self.max_continuity_gap_s),
            ("downgrade_stable_s", self.downgrade_stable_s),
        ):
            if wert > _MAX_ZEIT_S:
                raise ConfigError(
                    f"Hysterese-Parameter '{feld}' muss <= {_MAX_ZEIT_S} s (24 h) sein, "
                    f"ist aber {wert!r}"
                )
        # Plausibilitäts-Obergrenze für die °C-Marge: ein zu großer Deadband würde eine
        # Rückstufung faktisch nie bestätigen (Anzeige bliebe dauerhaft auf der höheren Stufe).
        if self.downgrade_undershoot_c > _MAX_UNDERSHOOT_C:
            raise ConfigError(
                f"Hysterese-Parameter 'downgrade_undershoot_c' muss <= {_MAX_UNDERSHOOT_C} °C "
                f"sein, ist aber {self.downgrade_undershoot_c!r}"
            )
        # Cross-Field: die Kontinuitäts-Lücke muss mindestens den On-Delay abdecken —
        # sonst bricht jeder Poll die Kontinuität, der On-Delay akkumuliert nie und es
        # feuert NIE ein Alarm (Under-Alarm). Laut scheitern statt still nie alarmieren.
        if self.max_continuity_gap_s < self.on_delay_s:
            raise ConfigError(
                "Hysterese-Parameter 'max_continuity_gap_s' muss >= 'on_delay_s' sein, ist "
                f"aber {self.max_continuity_gap_s!r} < {self.on_delay_s!r}"
            )


@dataclass(frozen=True)
class DatenqualitaetSchwellen:
    stale_timeout_s: float
    max_temp_jump_c_per_min: float
    flatline_timeout_min: float
    flatline_epsilon_c: float
    max_clock_skew_s: float
    min_plausible_dew_point_c: float


@dataclass(frozen=True)
class PlausibilitaetSchwellen:
    min_temp_c: float
    max_temp_c: float
    min_humidity_pct: float
    max_humidity_pct: float
    min_pressure_hpa: float
    max_pressure_hpa: float


@dataclass(frozen=True)
class BetriebParameter:
    """Laufzeit-/Betriebsparameter (P0-a): Poll-Kadenz des Schedulers.

    `poll_interval_s` = Intervall, in dem der Scheduler G1 pollt und neu bewertet (Contract:
    G1 ≤ 30 s). Parametrierbar (NF-05), nicht hardcodiert. Muss > 0 und endlich sein; die
    Kopplung an die Alarm-Hysterese (poll_interval_s <= max_continuity_gap_s) prüft
    `Thresholds` querschnittlich.
    """

    poll_interval_s: float

    def __post_init__(self) -> None:
        if isinstance(self.poll_interval_s, bool):
            raise ConfigError("Betriebs-Parameter 'poll_interval_s' darf kein bool sein")
        if not math.isfinite(self.poll_interval_s):
            raise ConfigError(
                f"Betriebs-Parameter 'poll_interval_s' muss endlich sein, "
                f"ist aber {self.poll_interval_s!r}"
            )
        if self.poll_interval_s <= 0:
            raise ConfigError(
                f"Betriebs-Parameter 'poll_interval_s' muss > 0 sein, "
                f"ist aber {self.poll_interval_s!r}"
            )
        if self.poll_interval_s > _MAX_ZEIT_S:
            raise ConfigError(
                f"Betriebs-Parameter 'poll_interval_s' muss <= {_MAX_ZEIT_S} s sein, "
                f"ist aber {self.poll_interval_s!r}"
            )


@dataclass(frozen=True)
class Thresholds:
    vereisung: VereisungsSchwellen
    prognose: PrognoseSchwellen
    hysterese: HystereseParameter
    datenqualitaet: DatenqualitaetSchwellen
    plausibilitaet: PlausibilitaetSchwellen
    betrieb: BetriebParameter

    def __post_init__(self) -> None:
        # Cross-Section (NF-01): pollt das System langsamer als die Kontinuitäts-Lücke der
        # Alarm-Hysterese, bricht jeder Poll die Eskalations-Kontinuität -> es feuert nie ein
        # Alarm (stiller Under-Alarm). Erst mit poll_interval_s in der Config (P0-a) ist dieser
        # zuvor unprüfbare Invariant (HystereseParameter-Doc) erzwingbar.
        if self.betrieb.poll_interval_s > self.hysterese.max_continuity_gap_s:
            raise ConfigError(
                "Config-Inkonsistenz: betrieb.poll_interval_s "
                f"({self.betrieb.poll_interval_s!r}) > hysterese.max_continuity_gap_s "
                f"({self.hysterese.max_continuity_gap_s!r}) -> Alarm-Kontinuität bricht je Poll"
            )
        # Cross-Section (NF-01): max_continuity_gap_s muss mindestens eine Stale-Phase (bis
        # stale_timeout_s) abdecken, damit eine einzelne Stale-Episode die Eskalations-
        # Kontinuität nicht bricht. (Ein REALER Ausfall, dessen Lücke max_gap übersteigt, setzt
        # den On-Delay bewusst zurück -> K1-Anti-Chattering, fail-safe: Anzeige bleibt UNKNOWN,
        # nie GRÜN. Diese Grenze bindet die Config-Größe, nicht die reale Ausfalldauer.)
        if self.hysterese.max_continuity_gap_s < self.datenqualitaet.stale_timeout_s:
            raise ConfigError(
                "Config-Inkonsistenz: hysterese.max_continuity_gap_s "
                f"({self.hysterese.max_continuity_gap_s!r}) < datenqualitaet.stale_timeout_s "
                f"({self.datenqualitaet.stale_timeout_s!r}) -> Stale-Phase bricht Alarm-Kontinuität"
            )
        # Cross-Section (FA-06/NF-01): die Prognose-Vorwarnung feuert bei forecast <= t_s_grenz_c.
        # Liegt die Schwelle UNTER dem Gefrierpunkt, warnt die 30-min-Prognose erst, wenn die
        # Oberfläche ohnehin schon gefriert -> die Vorwarnung wäre still neutralisiert.
        if self.prognose.t_s_grenz_c < self.vereisung.t_s_gefrierpunkt_c:
            raise ConfigError(
                "Config-Inkonsistenz: prognose.t_s_grenz_c "
                f"({self.prognose.t_s_grenz_c!r}) < vereisung.t_s_gefrierpunkt_c "
                f"({self.vereisung.t_s_gefrierpunkt_c!r}) -> 30-min-Vorwarnung still abgeschaltet"
            )


# Pflicht-Abschnitte der Config und ihr jeweiliger Zieltyp.
# Vereisungs-/Prognose-Schwellen (DTB-38) + Hysterese-Parameter (DTB-27) + Datenqualitaet/
# Plausibilitaet (DTB-13/58/60). Taupunkt-Konstanten gehören in ihre eigenen Tasks und
# werden dort von den jeweils Zuständigen ergänzt.
_SECTIONS: dict[str, type[Any]] = {
    "vereisung": VereisungsSchwellen,
    "prognose": PrognoseSchwellen,
    "hysterese": HystereseParameter,
    "datenqualitaet": DatenqualitaetSchwellen,
    "plausibilitaet": PlausibilitaetSchwellen,
    "betrieb": BetriebParameter,
}


def load_thresholds(path: Path | str | None = None) -> Thresholds:
    """Lädt die Schwellenwerte aus der JSON-Config (Default oder eigener Pfad).

    Scheitert *laut* mit `ConfigError`, wenn die Datei fehlt, kein gültiges JSON-Objekt
    ist, ein Pflicht-Abschnitt/-Schlüssel fehlt oder ein Schwellenwert keine Zahl ist —
    bewusst kein stiller Default (NF-01-Geist).
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {config_path}")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Konfigurationsdatei ist kein gültiges JSON: {config_path} ({exc})"
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Konfiguration muss ein JSON-Objekt sein: {config_path}")

    sektionen = {name: _baue_sektion(name, cls, raw) for name, cls in _SECTIONS.items()}
    return Thresholds(**sektionen)


def _baue_sektion[T](name: str, cls: type[T], raw: dict[str, Any]) -> T:
    """Validiert Struktur + numerische Werte eines Abschnitts und baut das Dataclass-Objekt."""
    if name not in raw:
        raise ConfigError(f"Pflicht-Abschnitt fehlt in Konfiguration: '{name}'")
    daten = raw[name]
    if not isinstance(daten, dict):
        raise ConfigError(
            f"Abschnitt '{name}' muss ein JSON-Objekt sein, ist aber {type(daten).__name__}"
        )
    erwartet = {f.name for f in fields(cls)}
    fehlend = erwartet - daten.keys()
    if fehlend:
        raise ConfigError(f"Abschnitt '{name}': fehlende Pflicht-Schlüssel {sorted(fehlend)}")
    # Unbekannte/vertippte Schlüssel laut ablehnen (NF-05: eine Safety-Config darf einen
    # vertippten Key nicht still verwerfen -> Operator glaubt sonst, eine Schwelle geändert
    # zu haben, der Default bleibt aktiv). Spiegelt extra='forbid' der Pydantic-Modelle.
    # Ausnahme: '_'-praefixierte Keys sind Kommentar-/Metadaten-Konvention (wie auf Top-Level)
    # und werden auch im Abschnitt toleriert; echte Schwellen-Keys beginnen nie mit '_', der
    # Tippfehler-Schutz fuer reale Keys (z. B. 'off_delay_s') bleibt erhalten.
    unerwartet = {k for k in daten.keys() - erwartet if not k.startswith("_")}
    if unerwartet:
        raise ConfigError(f"Abschnitt '{name}': unbekannte Schlüssel {sorted(unerwartet)}")
    werte = {feld: daten[feld] for feld in erwartet}
    # Aufgelöste Typ-Hinweise (keine Strings) fuer robusten Ganzzahl-Check.
    # Bei `from __future__ import annotations` liefert f.type nur einen String;
    # get_type_hints() wertet Annotationen aus und gibt echte Typ-Objekte zurueck.
    # Ein Feld vom Typ `int | None` ist dann NICHT mehr `is int` (L-1).
    feld_typen = get_type_hints(cls)
    for feld, wert in werte.items():
        # bool ist in Python ein int-Subtyp, soll aber keine gültige Schwelle sein.
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            raise ConfigError(
                f"Abschnitt '{name}', Schlüssel '{feld}': Schwellenwert muss eine Zahl sein, "
                f"ist aber {type(wert).__name__} ({wert!r})"
            )
        # Ganzzahl-Felder (z. B. prognose.min_points): ein JSON-Float wie 3.0 ist eine
        # Fehlkonfiguration -> direkt hier ablehnen (einstufiges Typ-Gate), statt erst im
        # Sektions-Validator aufzufangen (DTB-33 Review LOW).
        if feld_typen[feld] is int and not isinstance(wert, int):
            raise ConfigError(
                f"Abschnitt '{name}', Schlüssel '{feld}': Ganzzahl erwartet, "
                f"ist aber {type(wert).__name__} ({wert!r})"
            )
        # NaN/inf unterlaufen jeden Vergleich (NaN < x ist immer False -> fail-open in der
        # Bewertung) -> für ALLE Schwellen-Sektionen ablehnen, nicht nur Hysterese.
        if not math.isfinite(wert):
            raise ConfigError(
                f"Abschnitt '{name}', Schlüssel '{feld}': Schwellwert muss endlich sein, "
                f"ist aber {wert!r}"
            )

    obj = cls(**werte)
    # Sektionsspezifische Plausibilitaet: Datenqualitaet-Grenzwerte muessen positiv
    # sein, damit die Fail-safe-Logik (DTB-13) nicht ins Gegenteil verkehrt.
    if cls is DatenqualitaetSchwellen:
        _validate_datenqualitaet(obj)
    elif cls is PlausibilitaetSchwellen:
        _validate_plausibilitaet(obj)
    elif cls is PrognoseSchwellen:
        _validate_prognose(obj)

    return obj


def _validate_prognose(schwellen: PrognoseSchwellen) -> None:
    """Prueft die Trendparameter (DTB-33): Fenster/Horizont positiv, min_points >= 2.

    Unplausible Werte wuerden die 30-min-Vorwarnung praktisch abschalten (NF-01):
    ein nicht-positives Fenster/Horizont oder weniger als zwei Stuetzstellen
    machen eine lineare Regression unmoeglich -> laut scheitern statt still leer.
    Die Vorwarn-Schwelle t_s_grenz_c muss zudem in einem physikalisch plausiblen
    Oberflaechentemp-Bereich liegen, sonst feuert die Prognose nie (FA-06).
    """
    if not _MIN_PLAUSIBLE_SURFACE_TEMP_C <= schwellen.t_s_grenz_c <= _MAX_PLAUSIBLE_SURFACE_TEMP_C:
        raise ConfigError(
            f"prognose.t_s_grenz_c muss zwischen {_MIN_PLAUSIBLE_SURFACE_TEMP_C} und "
            f"{_MAX_PLAUSIBLE_SURFACE_TEMP_C} °C liegen, ist aber {schwellen.t_s_grenz_c!r}"
        )
    _require_positive(schwellen.trend_window_min, "prognose.trend_window_min", upper=1_440)
    _require_positive(schwellen.horizon_min, "prognose.horizon_min", upper=1_440)
    # Cross-Field (NF-01): der Horizont darf nicht weiter reichen als das Datenfenster,
    # aus dem die Regression gespeist wird. horizon_min > trend_window_min extrapoliert die
    # T_s-Gerade um ein Vielfaches ueber den beobachteten Zeitraum hinaus (z. B. 60-min-Horizont
    # aus 10-min-Daten) -> statistisch unbelastbar. Laut scheitern statt still eine fragwuerdige
    # Vorwarnung liefern (der isfinite-Schutz am Ausgang bleibt, aber die Konfig ist falsch).
    if schwellen.horizon_min > schwellen.trend_window_min:
        raise ConfigError(
            "prognose.horizon_min darf nicht groesser als prognose.trend_window_min sein "
            f"({schwellen.horizon_min!r} > {schwellen.trend_window_min!r})"
        )
    # Ganzzahl- und Bereichspruefung fuer min_points/max_readings_limit.
    # isinstance(int) ist bereits in _baue_sektion erledigt (L-3); hier bleiben nur
    # die sektionsspezifischen semantischen Grenzen.
    if schwellen.min_points < 2:
        raise ConfigError(
            "prognose.min_points muss mindestens 2 sein (Regression braucht 2 Punkte)"
        )
    if schwellen.min_points > 100:
        raise ConfigError(
            "prognose.min_points darf nicht groesser als 100 sein "
            "(sonst wird die Prognose praktisch abgeschaltet, NF-01)"
        )
    # max_readings_limit begrenzt die DB-Last bei get_since; sie muss ausreichend gross
    # sein, um min_points Stuetzstellen zu liefern, sonst wird die Prognose still abgeschaltet.
    if schwellen.max_readings_limit < schwellen.min_points:
        raise ConfigError(
            "prognose.max_readings_limit muss mindestens so gross wie min_points sein"
        )
    if schwellen.max_readings_limit > 10_000:
        raise ConfigError(
            "prognose.max_readings_limit darf nicht groesser als 10000 sein "
            "(DB-Lastbegrenzung, NF-01)"
        )


def _validate_datenqualitaet(schwellen: DatenqualitaetSchwellen) -> None:
    """Prueft, dass Datenqualitaet-Schwellen keine ungueltigen Grenzwerte enthalten.

    Die Obergrenzen sind bewusst grosszuegig gewaehlt (NF-05: finale Werte kommen
    von G1), verhindern aber offensichtliche Fehlkonfigurationen, die Stale-
    oder Sprung-Erkennung praktisch abschalten wuerden (NF-01).
    """
    _require_positive(schwellen.stale_timeout_s, "datenqualitaet.stale_timeout_s", upper=86_400)
    _require_positive(
        schwellen.max_temp_jump_c_per_min,
        "datenqualitaet.max_temp_jump_c_per_min",
        upper=100.0,
    )
    _require_positive(
        schwellen.flatline_timeout_min, "datenqualitaet.flatline_timeout_min", upper=1_440
    )
    _require_non_negative(
        schwellen.flatline_epsilon_c, "datenqualitaet.flatline_epsilon_c", upper=10.0
    )
    _require_positive(schwellen.max_clock_skew_s, "datenqualitaet.max_clock_skew_s", upper=3_600)
    if not -100.0 <= schwellen.min_plausible_dew_point_c <= 50.0:
        raise ConfigError(
            "datenqualitaet.min_plausible_dew_point_c muss zwischen -100.0 und 50.0 liegen"
        )


def _validate_plausibilitaet(schwellen: PlausibilitaetSchwellen) -> None:
    """Prueft, dass Plausibilitaets-Grenzen sinnvoll sind (min < max + Absolutgrenzen).

    Die konkreten Werte kommen von G1 (Sensorik); hier wird nur verhindert,
    dass aus Versehen Min/Max vertauscht werden oder physikalisch unsinnige
    Werte konfiguriert werden und die Validierung dadurch permanent alles
    verwirft (NF-01).
    """
    if schwellen.min_temp_c >= schwellen.max_temp_c:
        raise ConfigError("plausibilitaet.min_temp_c muss kleiner als max_temp_c sein")
    if not -100.0 <= schwellen.min_temp_c <= 100.0:
        raise ConfigError("plausibilitaet.min_temp_c muss zwischen -100.0 und 100.0 liegen")
    if not -100.0 <= schwellen.max_temp_c <= 100.0:
        raise ConfigError("plausibilitaet.max_temp_c muss zwischen -100.0 und 100.0 liegen")

    if schwellen.min_humidity_pct >= schwellen.max_humidity_pct:
        raise ConfigError("plausibilitaet.min_humidity_pct muss kleiner als max_humidity_pct sein")
    _require_non_negative(
        schwellen.min_humidity_pct, "plausibilitaet.min_humidity_pct", upper=100.0
    )
    _require_non_negative(
        schwellen.max_humidity_pct, "plausibilitaet.max_humidity_pct", upper=100.0
    )

    if schwellen.min_pressure_hpa >= schwellen.max_pressure_hpa:
        raise ConfigError("plausibilitaet.min_pressure_hpa muss kleiner als max_pressure_hpa sein")
    # Obergrenze knapp ueber dem hoechsten je auf Meereshoehe gemessenen Luftdruck
    # (~1085 hPa, Weltrekord). Hoehere Werte sind physikalisch unsinnig und deuten auf
    # eine Fehlkonfiguration hin -> laut scheitern statt durchwinken (NF-01, DTB-93 LOW).
    _require_positive(schwellen.min_pressure_hpa, "plausibilitaet.min_pressure_hpa", upper=1100.0)
    _require_positive(schwellen.max_pressure_hpa, "plausibilitaet.max_pressure_hpa", upper=1100.0)


def _require_positive(value: float, name: str, upper: float) -> None:
    if value <= 0:
        raise ConfigError(f"{name} muss groesser als 0 sein")
    if value > upper:
        raise ConfigError(f"{name} darf nicht groesser als {upper} sein")


def _require_non_negative(value: float, name: str, upper: float) -> None:
    if value < 0:
        raise ConfigError(f"{name} darf nicht negativ sein")
    if value > upper:
        raise ConfigError(f"{name} darf nicht groesser als {upper} sein")
