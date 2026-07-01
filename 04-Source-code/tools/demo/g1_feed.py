"""g1_feed.py — cross-platform Demo-Feed + Feature-Showcase fuer das G2-Backend.

Loest das Windows-only `Alarmsystem-Demo/feed.ps1` ab (Variante A) und ergaenzt einen
zeitgesteuerten Feature-Showcase. EIN Codebase fuer Windows (start.ps1) UND Pi
(testrun-sim.sh) — kein Doppelpflege-Skript mehr.

Zwei Modi:
  --mode live      Living-Feed: rampt den G1-Sim-State sanft Richtung des in
                   scenario.txt gewaehlten Presets, mit Dither > flatline_epsilon,
                   sodass der Flatline-Fail-safe (NF-01) den Feed nicht als
                   eingefroren verwirft. Mit --profile winter faehrt ein
                   realistischer Winter-Tagesgang die Ampelstufen selbstaendig
                   durch (statt scenario.txt zu folgen).
  --mode showcase  Feature-Showcase: faehrt getaktet gruen -> thresholds -> gelb ->
                   orange -> rot -> ack -> stale -> fault -> recovery -> readings,
                   wartet die ECHTEN Timings ab (Poll 30 s, On-Delay 60 s) und prueft
                   jeden Schritt aktiv gegen die /v1-API (self-checking, PASS/FAIL).

Die reine Ramp-/Dither-/Preset-Logik liegt netzfrei in feed_core.py (getestet in
tests/test_demo_feed.py gegen die echte Vereisungskaskade assess_ice_risk).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

from tools.demo.feed_core import (
    DEFAULT_INTERVAL_S,
    PRESETS,
    FeedState,
    next_state,
)

# stdout robust auf UTF-8 stellen (Windows-Konsole ist per Default cp1252 -> Umlaute
# im Narrations-Text wuerden sonst '?' oder einen UnicodeEncodeError erzeugen).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except (AttributeError, ValueError):  # pragma: no cover - aeltere/exotische Streams
    pass


def _repo_root() -> Path:
    """04-Source-code/ (tools/demo/g1_feed.py -> parents[2])."""
    return Path(__file__).resolve().parents[2]


def _default_state_path() -> Path:
    return _repo_root() / "tools" / "g1_sim" / "g1_state.json"


def _default_scenario_path() -> Path:
    return _repo_root() / "tools" / "g1_sim" / "scenario.txt"


# --- State-IO (atomar, damit der Sim nie halb-geschriebenes JSON liest) -------


def write_state(path: Path, obj: dict) -> None:
    """Schreibt den Snapshot atomar (temp + os.replace) als kompaktes JSON."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="ascii")
    os.replace(tmp, path)


def read_state(path: Path) -> dict | None:
    """Liest den aktuellen State (fuer nahtlosen Wiederanlauf) oder None."""
    try:
        return json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError):
        return None


def read_scenario(path: Path, fallback: str = "red") -> str:
    """Liest das 1-Wort-Szenario; unbekannt/fehlend -> fallback."""
    try:
        raw = path.read_text(encoding="ascii").strip().lower()
    except OSError:
        return fallback
    return raw if raw in PRESETS else fallback


# --- Modus 1: Living-Feed -----------------------------------------------------

# Winter-Tagesgang (--profile winter): zyklischer Ablauf (Szenario, Sekunden), der die
# naechtliche Abkuehlung durch die Ampelkaskade und die morgendliche Erholung nachbildet.
# Die sanften Rampen + der Dither erzeugen "realistische Schwankungen im Winter".
WINTER_CYCLE: list[tuple[str, float]] = [
    ("green", 120.0),  # milder Abend, Oberflaeche ueber Gefrierpunkt
    ("yellow", 120.0),  # Abkuehlung Richtung 0 C (grenzwertig)
    ("orange", 150.0),  # naechtlicher Reifansatz (gefroren + Feuchte)
    ("red", 120.0),  # tiefste Nacht: aktive Eisbildung
    ("orange", 120.0),  # nachlassend
    ("yellow", 120.0),  # Morgendaemmerung, Erwaermung
]


def winter_scenario(elapsed_s: float) -> str:
    """Bildet die verstrichene Zeit auf das aktuelle Winter-Zyklus-Szenario ab."""
    period = sum(dur for _, dur in WINTER_CYCLE)
    pos = elapsed_s % period
    for scenario, dur in WINTER_CYCLE:
        if pos < dur:
            return scenario
        pos -= dur
    return WINTER_CYCLE[-1][0]  # pragma: no cover - Rundungsrest


def run_live(state_path: Path, scenario_path: Path, interval: int, profile: str | None) -> None:
    """Endlos-Loop: rampt den State Richtung Szenario-Preset und schreibt ihn getaktet."""
    state = FeedState.from_snapshot(read_state(state_path))
    tick = 0
    start = time.monotonic()
    mode = f"profile={profile}" if profile else f"scenario={scenario_path}"
    print(f"[live] Feed laeuft ({mode}, interval={interval}s). Strg+C zum Beenden.")
    while True:
        if profile == "winter":
            scenario = winter_scenario(time.monotonic() - start)
        else:
            scenario = read_scenario(scenario_path)
        snap = next_state(state, PRESETS[scenario], tick)
        write_state(state_path, snap)
        tick += 1
        time.sleep(interval)


# --- Modus 2: Feature-Showcase (self-checking) --------------------------------

_ACK_OPERATOR = "Demo-Operator"
# Grosszuegige Wartezeiten: der Backend-Poll ist 30 s, die Anzeige-Hysterese (On-Delay)
# 60 s -> eine Eskalation braucht real ~90 s, bis sie in assessment/current sichtbar wird.
_TIMEOUT_NORMAL_S = 120
_TIMEOUT_ESCALATE_S = 240


class ShowcaseResult:
    """Sammelt PASS/FAIL je Schritt fuer die Schluss-Zusammenfassung."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def record(self, step: str, ok: bool, detail: str) -> bool:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {step}: {detail}")
        self.rows.append((step, ok, detail))
        return ok

    def note(self, text: str) -> None:
        print(f"  [ -- ] {text}")

    @property
    def failed(self) -> list[str]:
        return [step for step, ok, _ in self.rows if not ok]


class Showcase:
    """Treibt den Feed getaktet durch alle Features und prueft die /v1-API live."""

    def __init__(self, client: httpx.Client, state_path: Path, interval: int) -> None:
        self.client = client
        self.state_path = state_path
        self.interval = interval
        self.state = FeedState.from_snapshot(read_state(state_path))
        self.tick = 0
        self.res = ShowcaseResult()

    # -- Low-level HTTP ----------------------------------------------------

    def _get(self, path: str, **params: object) -> httpx.Response | None:
        try:
            return self.client.get(path, params=params or None)
        except httpx.HTTPError as exc:
            print(f"  [ -- ] GET {path} fehlgeschlagen: {exc}")
            return None

    def current(self) -> dict | None:
        """assessment/current als dict, oder None bei 503/Fehler (noch keine Daten)."""
        resp = self._get("/v1/assessment/current")
        if resp is None or resp.status_code != 200:
            return None
        return resp.json()

    # -- Feed-Treiber ------------------------------------------------------

    def _tick_feed(self, scenario: str) -> None:
        snap = next_state(self.state, PRESETS[scenario], self.tick)
        write_state(self.state_path, snap)
        self.tick += 1

    def drive_until(self, scenario: str, predicate, timeout: int):
        """Rampt Richtung Szenario und pollt current, bis predicate(obs) True ist.

        Haelt den Feed dabei lebendig (Dither) und gibt die erste passende
        Beobachtung zurueck oder None bei Timeout.
        """
        deadline = time.monotonic() + timeout
        obs: dict | None = None
        while time.monotonic() < deadline:
            self._tick_feed(scenario)
            time.sleep(self.interval)
            obs = self.current()
            if obs is not None and predicate(obs):
                return obs
        return obs if (obs is not None and predicate(obs)) else None

    # -- Einzelschritte ----------------------------------------------------

    def step_health(self) -> None:
        resp = self._get("/v1/health")
        ok = resp is not None and resp.status_code == 200 and resp.json().get("status") == "ok"
        self.res.record("health", bool(ok), "GET /v1/health -> 200 {status: ok}")

    def step_level(self, scenario: str, expected: str, timeout: int) -> None:
        obs = self.drive_until(scenario, lambda o: o.get("risk_level") == expected, timeout)
        if obs is None:
            self.res.record(scenario, False, f"risk_level != {expected} (Timeout {timeout}s)")
            return
        factor = obs.get("driving_factor")
        self.res.record(scenario, True, f"risk_level={expected} (driving_factor={factor})")

    def step_forecast_opportunistic(self) -> None:
        """GELB-per-Prognose ist trend-/timingabhaengig -> nur beobachtend, nie FAIL."""
        obs = self.current()
        if obs and obs.get("risk_level") == "yellow" and obs.get("driving_factor") == "forecast":
            self.res.record("gelb-prognose", True, "GELB ueber 30-min-Prognose beobachtet")
        else:
            self.res.note("gelb-prognose: nicht separat erzwungen (Trend-/Timing-abhaengig)")

    def step_thresholds(self, api_key: str | None) -> None:
        get_resp = self._get("/v1/thresholds")
        self.res.record(
            "thresholds-get",
            get_resp is not None and get_resp.status_code == 200,
            f"GET /v1/thresholds -> {get_resp.status_code if get_resp else 'ERR'}",
        )
        # Unauth-Schreibversuch: 401 (Key konfiguriert) ODER 503 (Key nicht konfiguriert)
        # -> beides beweist, dass der Schreibpfad bewacht ist (NF-07, fail-safe-closed).
        body = {"changed_by": _ACK_OPERATOR, "name": "Showcase", "thresholds": {}}
        unauth = self.client.post("/v1/thresholds", json=body)
        self.res.record(
            "thresholds-unauth",
            unauth.status_code in (401, 503),
            f"POST ohne Key -> {unauth.status_code} (Schreibzugriff bewacht)",
        )
        if not api_key:
            self.res.note("thresholds-auth: uebersprungen (G2_API_KEY nicht gesetzt)")
            return
        # Autorisiert: die aktuelle Config zurueckschreiben (garantiert gueltig) -> 201.
        cfg = json.loads((_repo_root() / "config" / "thresholds.json").read_text(encoding="utf-8"))
        auth_body = {"changed_by": _ACK_OPERATOR, "name": "Showcase v1", "thresholds": cfg}
        auth = self.client.post(
            "/v1/thresholds", json=auth_body, headers={"Authorization": f"Bearer {api_key}"}
        )
        self.res.record(
            "thresholds-auth", auth.status_code == 201, f"POST mit Key -> {auth.status_code} (201)"
        )

    def _active_alarms(self) -> list[dict]:
        resp = self._get("/v1/alarms", state="active")
        return resp.json() if resp is not None and resp.status_code == 200 else []

    def step_alarm(self, severity: str) -> None:
        deadline = time.monotonic() + _TIMEOUT_NORMAL_S
        while time.monotonic() < deadline:
            hits = [a for a in self._active_alarms() if a.get("severity") == severity]
            if hits:
                self.res.record(
                    f"alarm-{severity}", True, f"aktiver {severity.upper()}-Alarm (SSE-Push)"
                )
                return
            time.sleep(self.interval)
        self.res.record(f"alarm-{severity}", False, f"kein aktiver {severity}-Alarm (Timeout)")

    def step_ack(self) -> None:
        alarms = self._active_alarms()
        if not alarms:
            self.res.record("ack", False, "kein aktiver Alarm zum Quittieren")
            return
        alarm_id = max(a["id"] for a in alarms)
        body = {"operator": _ACK_OPERATOR, "note": "Showcase-Quittierung"}
        first = self.client.post(f"/v1/alarms/{alarm_id}/ack", json=body)
        self.res.record(
            "ack", first.status_code == 200, f"POST ack {alarm_id} -> {first.status_code} (200)"
        )
        second = self.client.post(f"/v1/alarms/{alarm_id}/ack", json=body)
        self.res.record(
            "double-ack",
            second.status_code == 409,
            f"erneuter ack -> {second.status_code} (409, NF-09)",
        )

    def step_failsafe(self, scenario: str, checker, label: str) -> None:
        obs = self.drive_until(scenario, checker, _TIMEOUT_NORMAL_S)
        if obs is None:
            self.res.record(scenario, False, f"{label} (Timeout {_TIMEOUT_NORMAL_S}s)")
            return
        self.res.record(
            scenario, True, f"{label}: risk_level=unknown, {self._failsafe_detail(obs)}"
        )

    @staticmethod
    def _failsafe_detail(obs: dict) -> str:
        return f"is_stale={obs.get('is_stale')}, sensor_status={obs.get('sensor_status')}"

    def step_audit(self) -> None:
        resp = self._get("/v1/audit", limit=200)
        if resp is None or resp.status_code != 200:
            self.res.record("audit", False, "GET /v1/audit fehlgeschlagen")
            return
        seen = {e.get("event_type") for e in resp.json()}
        wanted = {
            "reading_ingested",
            "assessment_made",
            "alarm_raised",
            "alarm_acknowledged",
            "sensor_fault",
        }
        present = wanted & seen
        self.res.record(
            "audit",
            present >= {"assessment_made", "alarm_raised", "alarm_acknowledged"},
            f"event_types: {sorted(present)}",
        )

    def step_readings(self) -> None:
        resp = self._get("/v1/readings", limit=10, order="desc")
        ok = resp is not None and resp.status_code == 200 and len(resp.json()) > 0
        n = len(resp.json()) if resp is not None and resp.status_code == 200 else 0
        self.res.record("readings", bool(ok), f"GET /v1/readings -> {n} Eintraege (Historie)")

    # -- Ablauf ------------------------------------------------------------

    def run(self, api_key: str | None) -> int:
        print("=== Feature-Showcase G2 (echte Timings; Durchlauf ~10-12 min) ===")
        print("Voraussetzung: Stack laeuft (start.ps1) und KEIN Live-Feed schreibt parallel.\n")
        self.step_health()
        print("\n-- Ampel GRUEN --")
        self.step_level("green", "green", _TIMEOUT_NORMAL_S)
        print("\n-- Thresholds (lesen + Auth-Gate) --")
        self.step_thresholds(api_key)
        print("\n-- Ampel GELB --")
        self.step_level("yellow", "yellow", _TIMEOUT_NORMAL_S)
        self.step_forecast_opportunistic()
        print("\n-- Ampel ORANGE + WARNING-Alarm --")
        self.step_level("orange", "orange", _TIMEOUT_ESCALATE_S)
        self.step_alarm("warning")
        print("\n-- Ampel ROT + CRITICAL-Alarm --")
        self.step_level("red", "red", _TIMEOUT_ESCALATE_S)
        self.step_alarm("critical")
        print("\n-- Quittierung (200) + Double-Ack (409) --")
        self.step_ack()
        print("\n-- Fail-safe STALE --")
        self.step_failsafe(
            "stale",
            lambda o: o.get("risk_level") == "unknown" and o.get("is_stale") is True,
            "veraltete Daten",
        )
        print("\n-- Fail-safe FAULT --")
        self.step_failsafe(
            "fault",
            lambda o: o.get("risk_level") == "unknown" and o.get("sensor_status") == "fault",
            "Sensor-Fault",
        )
        print("\n-- Recovery (unknown -> GRUEN, keine klebende Ampel) --")
        self.step_level("green", "green", _TIMEOUT_NORMAL_S)
        print("\n-- Audit + Readings --")
        self.step_audit()
        self.step_readings()
        return self._summary()

    def _summary(self) -> int:
        failed = self.res.failed
        print("\n=== Ergebnis ===")
        if not failed:
            print(f"ALLE {len(self.res.rows)} Schritte PASS.")
            return 0
        print(f"{len(failed)} von {len(self.res.rows)} Schritten FAIL: {', '.join(failed)}")
        return 1


def run_showcase(base_url: str, state_path: Path, interval: int, api_key: str | None) -> int:
    """Baut den HTTP-Client und startet den Showcase; Return = Prozess-Exitcode."""
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        return Showcase(client, state_path, interval).run(api_key)


# --- CLI ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="G1-Demo-Feed + Feature-Showcase (G2)")
    parser.add_argument("--mode", choices=("live", "showcase"), default="live")
    parser.add_argument("--profile", choices=("winter",), default=None, help="Live: Auto-Tagesgang")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S, help="Sekunden/Tick")
    parser.add_argument("--state", type=Path, default=_default_state_path(), help="g1_state.json")
    parser.add_argument("--scenario", type=Path, default=_default_scenario_path())
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Showcase: Backend-URL")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("G2_API_KEY"),
        help="Showcase: API-Key fuer den autorisierten Thresholds-POST (sonst G2_API_KEY).",
    )
    args = parser.parse_args()

    if args.mode == "showcase":
        raise SystemExit(run_showcase(args.base_url, args.state, args.interval, args.api_key))
    try:
        run_live(args.state, args.scenario, args.interval, args.profile)
    except KeyboardInterrupt:
        print("\n[live] beendet.")


if __name__ == "__main__":
    main()
