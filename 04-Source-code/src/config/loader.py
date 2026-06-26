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
from typing import Any

# config/thresholds.json liegt zwei Ebenen über src/config/loader.py
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds.json"


class ConfigError(Exception):
    """Konfiguration fehlt oder ist ungültig — bewusst lautes Scheitern statt stiller Defaults."""


@dataclass(frozen=True)
class VereisungsSchwellen:
    t_s_gefrierpunkt_c: float
    t_s_gelb_auffang_c: float
    delta_t_kondensation_k: float
    delta_t_feucht_k: float


@dataclass(frozen=True)
class PrognoseSchwellen:
    t_s_grenz_c: float


@dataclass(frozen=True)
class HystereseParameter:
    """Entprellung/Hysterese der Alarm-Generierung (DTB-27, Schwellenwerte.md §2).

    Zeitkonstanten in Sekunden, Temperatur-Marge in °C. Gegen Chattering (ISA-18.2):
    Hochstufung (Auslösen) erst nach `on_delay_s` anhaltender Bedingung — von der
    Engine umgesetzt. `max_continuity_gap_s` begrenzt, wie lange eine Unsicherheits-
    /Stale-Phase (UNKNOWN) die laufende Eskalation einfrieren darf, ohne die Kontinuität
    zu brechen (Default = Stale-Timeout 120 s); danach ist ein frischer On-Delay nötig.
    Die Rückstufung (`downgrade_undershoot_c` um 0,5 °C unterschritten UND
    `downgrade_stable_s` stabil) ist **geplant** (DTB-27-Folgeschritt) und braucht eine
    Temperatur-Kopplung in der Bewertungsschicht; beide Felder sind dafür reserviert und
    werden von der aktuellen Engine noch NICHT ausgewertet. KEIN Auto-Clear (RB-01).
    """

    on_delay_s: float
    max_continuity_gap_s: float
    downgrade_stable_s: float  # reserviert: Rückstufungs-Stabilität (noch nicht ausgewertet)
    downgrade_undershoot_c: float  # reserviert: Rückstufungs-Marge (noch nicht ausgewertet)

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
            if not math.isfinite(wert):
                raise ConfigError(
                    f"Hysterese-Parameter '{feld}' muss endlich sein, ist aber {wert!r}"
                )
            if wert < 0:
                raise ConfigError(
                    f"Hysterese-Parameter '{feld}' muss >= 0 sein, ist aber {wert!r}"
                )


@dataclass(frozen=True)
class Thresholds:
    vereisung: VereisungsSchwellen
    prognose: PrognoseSchwellen
    hysterese: HystereseParameter


# Pflicht-Abschnitte der Config und ihr jeweiliger Zieltyp.
# Vereisungs-/Prognose-Schwellen (DTB-38) + Hysterese-Parameter (DTB-27). Weitere
# Parameter (Taupunkt-Konstanten, Datenstatus) gehören in ihre eigenen Tasks und
# werden dort von den jeweils Zuständigen ergänzt.
_SECTIONS: dict[str, type[Any]] = {
    "vereisung": VereisungsSchwellen,
    "prognose": PrognoseSchwellen,
    "hysterese": HystereseParameter,
}


def load_thresholds(path: Path | str | None = None) -> Thresholds:
    """Lädt die Schwellenwerte aus der JSON-Config (Default oder eigener Pfad).

    Scheitert *laut* mit `ConfigError`, wenn die Datei fehlt, kein gültiges JSON-Objekt
    ist, ein Pflicht-Abschnitt/-Schlüssel fehlt oder ein Schwellwert keine Zahl ist —
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


def _baue_sektion[T](name: str, cls: type[T], raw: dict) -> T:
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
    werte = {feld: daten[feld] for feld in erwartet}
    for feld, wert in werte.items():
        # bool ist in Python ein int-Subtyp, soll aber keine gültige Schwelle sein.
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            raise ConfigError(
                f"Abschnitt '{name}', Schlüssel '{feld}': Schwellwert muss eine Zahl sein, "
                f"ist aber {type(wert).__name__} ({wert!r})"
            )
    return cls(**werte)
