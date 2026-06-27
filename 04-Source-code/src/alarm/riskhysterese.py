"""Anzeige-Hysterese / Rückstufung der Risikostufe (DTB-27, Schwellenwerte.md §2).

Stabilisiert die *gemeldete* Risikostufe gegen Chattering (ISA-18.2): **hoch sofort**
(NF-01: ein realer Vereisungsbeginn wird ohne Verzögerung sichtbar), **runter erst**,
wenn die Stufe gegen ein um `downgrade_undershoot_c` (0,5 °C/K) in Sicherheitsrichtung
verschobenes Schwellen-Set fällt UND `downgrade_stable_s` (≥ 5 min) stabil bleibt.

Zustandsbehaftet, aber rein und deterministisch (Zeit wird als `jetzt` übergeben). Wrappt
die zustandslose Bewertung `assess_ice_risk` (DTB-38 bleibt zustandslos). Diese Stufe ist
für die Ampel (`GET /v1/assessment/current`, DTB-43) gedacht — NICHT für die
Alarm-Auslösung (die hat ihren eigenen On-Delay in `AlarmHysterese`). Hier liegt der
einzige Wohnort der Rückstufungs-Zeitkonstanten (`downgrade_*`).

Fail-safe: `UNKNOWN` (Stale/ungültig) wird IMMER sofort übernommen — Unsicherheit wird
nie durch die Rückstufung verzögert/verdeckt. Aus `UNKNOWN` heraus wird die nächste
gültige Stufe ebenfalls sofort übernommen (Recovery aus Unsicherheit).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from src.assessment.core import assess_ice_risk
from src.config.loader import HystereseParameter, Thresholds
from src.model.enums import RiskLevel

# Rangordnung der "Leiter" GRÜN < GELB < ORANGE < ROT. UNKNOWN ist orthogonal
# (Unsicherheit) und wird gesondert behandelt — nie über diesen Rang verglichen.
_RISK_RANG: dict[RiskLevel, int] = {
    RiskLevel.GREEN: 0,
    RiskLevel.YELLOW: 1,
    RiskLevel.ORANGE: 2,
    RiskLevel.RED: 3,
}


class RiskHysterese:
    """Entprellt die gemeldete Risikostufe: hoch sofort, runter mit Deadband + Stabilität."""

    def __init__(self, params: HystereseParameter) -> None:
        self._undershoot = params.downgrade_undershoot_c
        self._downgrade_stable = timedelta(seconds=params.downgrade_stable_s)
        self._current: RiskLevel | None = None
        # Zeitpunkt, seit dem die niedrigere Stufe das Deadband klar unterschreitet.
        self._downgrade_seit: datetime | None = None

    def bewerten(
        self,
        surface_temp_c: float,
        dew_point_c: float | None,
        thresholds: Thresholds,
        jetzt: datetime,
        forecast_surface_temp_c: float | None = None,
    ) -> RiskLevel:
        """Liefert die gedebouncte Risikostufe für `jetzt`.

        Raises:
            ValueError: wenn `jetzt` nicht zeitzonenbewusst ist (Contract §2a D: UTC).
            Der Aufrufer muss monoton steigende Zeit liefern (Poll-Schicht).
        """
        if jetzt.tzinfo is None:
            raise ValueError(
                "jetzt muss zeitzonenbewusst (UTC) sein — naive datetime nicht erlaubt."
            )
        jetzt = jetzt.astimezone(UTC)

        roh = assess_ice_risk(surface_temp_c, dew_point_c, thresholds, forecast_surface_temp_c)

        # Sofort übernehmen: Erstaufruf · UNKNOWN (Unsicherheit nie verzögern) · Recovery aus
        # UNKNOWN · Hochstufung oder gleiche Stufe. Nur eine ECHTE Herabstufung wird entprellt.
        if (
            self._current is None
            or roh is RiskLevel.UNKNOWN
            or self._current is RiskLevel.UNKNOWN
            or _RISK_RANG[roh] >= _RISK_RANG[self._current]
        ):
            self._current = roh
            self._downgrade_seit = None
            return self._current

        # Herabstufung: erst bestätigt, wenn die Stufe auch gegen die um `undershoot` in
        # Sicherheitsrichtung verschobenen Schwellen fällt (Deadband) — sonst halten.
        streng = assess_ice_risk(
            surface_temp_c, dew_point_c, self._verschoben(thresholds), forecast_surface_temp_c
        )
        # `streng is UNKNOWN` ist mit der aktuellen `assess_ice_risk`-Semantik unerreichbar:
        # UNKNOWN entsteht rein datengetrieben (nicht-endliches T_s/T_d) und ist damit für `roh`
        # und `streng` identisch — und `roh is UNKNOWN` ist oben bereits abgefangen. Der Guard
        # bleibt als Defense-in-Depth, falls assess_ice_risk künftig schwellenabhängig UNKNOWN
        # liefert: dann wird konservativ die aktuelle (höhere) Stufe gehalten.
        if streng is RiskLevel.UNKNOWN or _RISK_RANG[streng] >= _RISK_RANG[self._current]:
            self._downgrade_seit = None  # noch im Deadband -> kein stabiler Abstieg
            return self._current

        # Deadband überschritten -> Stabilität über `downgrade_stable_s` verlangen.
        if self._downgrade_seit is None:
            self._downgrade_seit = jetzt
            return self._current
        if jetzt - self._downgrade_seit >= self._downgrade_stable:
            # Auf die KONSERVATIVE (verschobene) Stufe absteigen, nicht auf `roh`. Bei einem
            # Mehrstufen-Abstieg liegt `streng` zwischen `roh` und `current`; so springt die
            # Anzeige nie unter die eigene Sicherheitsmarge — die nächste Stufe wird erst
            # übernommen, wenn auch das verschobene Set sie freigibt (jeder Deadband zählt).
            self._current = streng
            self._downgrade_seit = None
            return self._current
        return self._current

    def _verschoben(self, t: Thresholds) -> Thresholds:
        """Schwellen-Set, um `undershoot` in Sicherheitsrichtung verschoben (macht die
        höhere Stufe „klebrig": eine Herabstufung verlangt den 0,5-Deadband-Abstand)."""
        d = self._undershoot
        # Alle Schwellen um +d anheben = konservativ in Sicherheitsrichtung: Temperatur-Schwellen
        # höher (Herabstufung verlangt mehr „Auftauen"). Delta-Schwellen höher macht `delta_t <=
        # threshold` (Kaskade in assess_ice_risk) LEICHTER erfüllbar -> ROT/ORANGE wird schneller
        # klassifiziert -> die höhere Stufe wird „klebrig". In Summe muss eine Herabstufung das
        # Deadband klar unterschreiten.
        v = replace(
            t.vereisung,
            t_s_gefrierpunkt_c=t.vereisung.t_s_gefrierpunkt_c + d,
            t_s_gelb_auffang_c=t.vereisung.t_s_gelb_auffang_c + d,
            delta_t_kondensation_k=t.vereisung.delta_t_kondensation_k + d,
            delta_t_feucht_k=t.vereisung.delta_t_feucht_k + d,
        )
        p = replace(t.prognose, t_s_grenz_c=t.prognose.t_s_grenz_c + d)
        return replace(t, vereisung=v, prognose=p)
