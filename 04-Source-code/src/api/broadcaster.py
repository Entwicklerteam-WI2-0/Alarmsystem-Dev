"""In-Process Pub/Sub + SSE-Frame-Formatierung fuer den Live-Alarm-Stream (DTB-61, E-37).

`GET /v1/alarms/stream` (api/v1.py) pusht Alarme live an G3, statt sie pollen zu lassen.
Der Bewertungszyklus (`run_scheduler` in main.py, auf dem Event-Loop) ruft bei jedem neu
ausgeloesten Alarm `AlarmBroadcaster.publish(alarm)`; jeder offene SSE-Client haelt ueber
`subscribe()` ein Abo (eine `asyncio.Queue`) und konsumiert daraus via `sse_alarm_frames`.

Bewusste Scope-Grenzen:
- **Kein Replay-Puffer.** Nach einem Reconnect (Last-Event-ID) macht G3 den Resync ueber
  `GET /v1/alarms` (DTB-31, Sicherheits-Backstop, E-37) — der Stream ist Live-Push, nicht
  die Quelle der Wahrheit. Ein verpasstes Event holt der Resync, nicht der Stream.
- **Bounded Queue + Drop-oldest.** Ein langsamer/haengender Client darf den Broadcaster
  nicht unbegrenzt Speicher kosten; bei vollem Puffer faellt der AELTESTE Alarm raus
  (der neueste = relevanteste Lage ueberlebt). Der Resync deckt die Luecke.

RB-01: reiner Push/Lese-Pfad, kein Aktor. Thread: `publish` wird auf dem Event-Loop
aufgerufen (run_scheduler nach `asyncio.to_thread`) -> direkter `asyncio.Queue`-Zugriff
ist safe (kein cross-thread Put).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

from src.model.schemas import Alarm

logger = logging.getLogger(__name__)

# Alarme pro Client-Puffer, bevor Drop-oldest greift. Grosszuegig: ein gesunder Client
# leert die Queue sofort; der Puffer faengt nur kurze Lastspitzen / langsame Verbraucher ab.
_DEFAULT_MAX_QUEUE = 100

# Max. gleichzeitige SSE-Abos. Schutz gegen unbegrenztes Verbindungswachstum (Speicher/
# Ressourcen): G3 haelt im Normalbetrieb EINE Verbindung; der Spielraum deckt mehrere
# Operator-Screens + ueberlappende Reconnects ab. Darueber weist der Endpoint mit 503 ab.
_DEFAULT_MAX_SUBSCRIBERS = 64

# Heartbeat-Intervall (s): Contract ~15 s SSE-Kommentarzeile, damit G3 einen still
# gestorbenen Stream von einem nur ruhigen unterscheidet.
_HEARTBEAT_S = 15.0
_HEARTBEAT_FRAME = ":keep-alive\n\n"


class StreamCapacityError(Exception):
    """Obergrenze gleichzeitiger SSE-Abos erreicht.

    `reserve()` wirft sie, BEVOR ein Abo angelegt wird; der Endpoint (stream_alarms)
    faengt sie und antwortet contract-konform mit 503 (es beginnt kein StreamingResponse).
    """


class AlarmBroadcaster:
    """Verteilt ausgeloeste Alarme an alle offenen SSE-Abos (In-Process Pub/Sub)."""

    def __init__(
        self,
        max_queue: int = _DEFAULT_MAX_QUEUE,
        max_subscribers: int = _DEFAULT_MAX_SUBSCRIBERS,
    ) -> None:
        # list (nicht set): die Zustellreihenfolge ist die Abo-Reihenfolge — deterministisch
        # by design (fair: zuerst Verbundene zuerst), ohne White-Box-Reihenfolge-Hacks in Tests.
        # reserve() vergibt je Abo eine NEUE Queue -> keine Duplikate.
        self._subscribers: list[asyncio.Queue[Alarm]] = []
        self._max_queue = max_queue
        self._max_subscribers = max_subscribers

    @property
    def subscriber_count(self) -> int:
        """Anzahl aktuell offener Abos (fuer Tests/Diagnose)."""
        return len(self._subscribers)

    def publish(self, alarm: Alarm) -> None:
        """Verteilt einen Alarm an alle Abos — best-effort, NIE werfend (NF-01).

        Ein Fehler im Push darf den Bewertungszyklus nicht beenden: jede Exception wird
        geloggt, nicht propagiert. Bei vollem Client-Puffer wird der aelteste Alarm
        verworfen (Drop-oldest; der Resync via DTB-31 schliesst die Luecke).
        """
        if alarm.id is None:
            # Invariante am Ingress (Bug-Guard): nur persistierte Alarme (mit DB-id) duerfen
            # gestreamt werden. Best-effort (NF-01: nie werfend) -> an der Quelle loggen +
            # verwerfen, statt einen "id: None"-Event an ALLE Clients zu verteilen. _frame()
            # haelt als letzte Linie zusaetzlich dagegen (raise).
            logger.error(
                "Alarm ohne DB-id verworfen (nicht gestreamt) — Bug: publish vor Persistenz?"
            )
            return
        for queue in self._subscribers:
            try:
                if queue.full():
                    # Platz fuer den neuesten Alarm schaffen: aeltesten verwerfen.
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                    logger.warning(
                        "SSE-Client-Puffer voll -> aeltesten Alarm verworfen "
                        "(Client zu langsam; Resync via GET /v1/alarms deckt ab)."
                    )
                queue.put_nowait(alarm)
            except Exception:  # noqa: BLE001 - Push best-effort (NF-01): nie den Zyklus stoppen
                logger.exception("Alarm-Push an einen Abonnenten fehlgeschlagen (uebersprungen).")

    def reserve(self) -> asyncio.Queue[Alarm]:
        """Legt ein neues Abo an und gibt dessen Queue zurueck — synchron + atomar.

        Synchron (kein await) und damit race-frei auf dem Event-Loop: zwischen Kapazitaets-
        pruefung und Registrierung laeuft keine andere Coroutine, die das Limit unterlaufen
        koennte. Bei erreichter Obergrenze -> StreamCapacityError (Endpoint -> 503), statt den
        Broadcaster unbegrenzt wachsen zu lassen (Speicher-/Ressourcenschutz).
        """
        if len(self._subscribers) >= self._max_subscribers:
            raise StreamCapacityError(
                f"max. {self._max_subscribers} gleichzeitige SSE-Abos erreicht"
            )
        queue: asyncio.Queue[Alarm] = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.append(queue)
        return queue

    def release(self, queue: asyncio.Queue[Alarm]) -> None:
        """Meldet ein Abo ab (Verbindungsende) und gibt die Kapazitaet wieder frei.

        Idempotent (discard-Semantik): ein bereits abgemeldetes Abo wird ignoriert, statt
        wie `list.remove` mit ValueError zu scheitern.
        """
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Alarm]]:
        """Registriert ein Abo (via reserve) und baut es bei Verbindungsende garantiert ab.

        Dieselbe Kapazitaetsgrenze + Leak-Schutz wie reserve()/release(): die `finally`-
        Abmeldung verhindert, dass die Queue eines getrennten Clients zurueckbleibt und bei
        jedem `publish` weiter befuellt wird.

        Nutzungspfade (PR-Review): Im PRODUKTIONSpfad wird subscribe() NICHT verwendet — der
        Endpoint `stream_alarms` in `api/v1.py` ruft reserve()/release() DIREKT (reserve muss
        vor dem StreamingResponse laufen, um bei voller Kapazitaet noch ein 503 zu liefern).
        subscribe() ist die Test-Convenience-Naht; eine Aenderung an subscribe()/reserve()/
        release() muss daher BEIDE Nutzungspfade im Blick behalten.
        """
        queue = self.reserve()
        try:
            yield queue
        finally:
            self.release(queue)


def _frame(alarm: Alarm) -> str:
    """Ein SSE-Event: `id:` = Alarm-ID (Reconnect via Last-Event-ID), `data:` = Alarm-JSON.

    `data:` traegt exakt das eingefrorene `Alarm`-Schema (openapi.yaml: id, assessment_id,
    severity, raised_at, state) — `model_dump_json` ist die eine Serialisierung dieses
    Pydantic-Modells. Leerzeile (`\\n\\n`) schliesst das Event ab (SSE-Framing).
    """
    if alarm.id is None:
        # Invariante (-O-fest, raise statt assert wie main.py): nur persistierte Alarme
        # mit DB-id duerfen gestreamt werden. Sonst ginge "id: None" als SSE-Event-ID
        # raus, die G3s EventSource als Last-Event-ID speichern wuerde.
        raise ValueError("alarm.id muss gesetzt sein (DB-id) bevor gestreamt wird")
    return f"id: {alarm.id}\ndata: {alarm.model_dump_json()}\n\n"


async def sse_alarm_frames(
    queue: asyncio.Queue[Alarm],
    is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat_s: float = _HEARTBEAT_S,
) -> AsyncGenerator[str, None]:
    """Erzeugt SSE-Frames aus einem Abo-Queue, bis der Client die Verbindung trennt.

    Wartet je Runde bis `heartbeat_s` auf den naechsten Alarm; bleibt er aus, geht eine
    `:keep-alive`-Kommentarzeile raus (Liveness-Signal). `is_disconnected` wird zwischen
    den Frames geprueft, damit ein getrennter Client sauber beendet wird (das Abo raeumt
    der `subscribe()`-Kontextmanager im Aufrufer ab).

    Disconnect-Latenz: `is_disconnected` wird erst NACH dem `wait_for` geprueft -> ein nur
    per Poll als getrennt erkannter Client haelt seinen Subscriber-Slot bis zu `heartbeat_s`
    (~15 s) weiter. Im Normalbetrieb (G3 = 1 Verbindung, Cap 64) unkritisch; falls der Cap je
    nahe ausgeschoepft wird, koennte er bei vielen gleichzeitigen Disconnects kurz blockieren
    (dann engeren Disconnect-Poll erwaegen). Bei echtem HTTP-Disconnect raeumt Starlettes
    Task-Cancel sofort ab — diese Latenz betrifft nur den `is_disconnected`-Poll-Pfad.

    Entkoppelt von FastAPIs `Request` (nimmt nur ein `is_disconnected`-Callable) -> ohne
    HTTP-Stack unit-testbar.
    """
    while not await is_disconnected():
        try:
            alarm = await asyncio.wait_for(queue.get(), timeout=heartbeat_s)
        except TimeoutError:  # asyncio.wait_for wirft ab 3.11 die builtin TimeoutError
            # Leerlauf: Heartbeat statt Stille -> G3 erkennt eine lebende Verbindung.
            yield _HEARTBEAT_FRAME
            continue
        try:
            frame = _frame(alarm)
        except ValueError:
            # Resilienz: ein einzelner malformed Alarm (id=None, der publish() umgangen hat)
            # darf den LIVE-Stream nicht abreissen -> ueberspringen + loggen, damit G3 die
            # FOLGENDEN Alarme weiter erhaelt (NF-01-Geist: ein kaputtes Item kippt nicht den
            # ganzen Feed). publish() + _frame() bleiben die vorgelagerten Guards.
            logger.error("Malformed Alarm (ohne DB-id) im Stream uebersprungen.")
            continue
        yield frame
