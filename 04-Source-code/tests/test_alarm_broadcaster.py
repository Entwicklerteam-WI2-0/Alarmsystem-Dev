"""Tests fuer den In-Process-Alarm-Broadcaster + SSE-Frame-Generator (DTB-61).

`AlarmBroadcaster` ist das Pub/Sub hinter `GET /v1/alarms/stream` (E-37): der
Bewertungszyklus (run_scheduler, auf dem Event-Loop) ruft `publish(alarm)`; jeder
offene SSE-Client haelt ein `subscribe()`-Abo (asyncio.Queue) und konsumiert daraus.

Belegt:
- Fan-out an mehrere Abonnenten; Abbau des Abos beim Verbindungsende.
- Bounded Queue + Drop-oldest bei Ueberlauf (langsamer Client; Resync via DTB-31 deckt ab).
- `publish` ist best-effort (NF-01): nie werfend, auch ohne Abonnenten.
- `sse_alarm_frames` formatiert den Contract-Frame (`id:`/`data:` = Alarm-JSON) und
  sendet bei Leerlauf den Heartbeat-Kommentar (`:keep-alive`).

Bewusst ohne pytest-asyncio: jedes Szenario laeuft via `asyncio.run` (gleicher Loop wie
im Betrieb -> kein cross-thread Queue-Zugriff).
"""

import asyncio
import inspect
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from src.api.broadcaster import (
    _DEFAULT_MAX_QUEUE,
    _HEARTBEAT_S,
    AlarmBroadcaster,
    StreamCapacityError,
    _frame,
    sse_alarm_frames,
)
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from tests.sse_helpers import disconnect_after

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _alarm(alarm_id: int, severity: AlarmSeverity = AlarmSeverity.WARNING) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=alarm_id * 10,
        severity=severity,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )


async def _drain(gen: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in gen]


# ---------------------------------------------------------------------------
# AlarmBroadcaster — Pub/Sub
# ---------------------------------------------------------------------------


def test_publish_delivers_alarm_to_subscriber():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as queue:
            bc.publish(_alarm(1))
            got = await asyncio.wait_for(queue.get(), timeout=1)
        assert got.id == 1
        assert got.severity is AlarmSeverity.WARNING

    asyncio.run(scenario())


def test_publish_fans_out_to_all_subscribers():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as q1, bc.subscribe() as q2:
            assert bc.subscriber_count == 2
            bc.publish(_alarm(5))
            a1 = await asyncio.wait_for(q1.get(), timeout=1)
            a2 = await asyncio.wait_for(q2.get(), timeout=1)
        assert a1.id == 5 and a2.id == 5

    asyncio.run(scenario())


def test_subscribe_cleans_up_on_exit():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        assert bc.subscriber_count == 0
        async with bc.subscribe():
            assert bc.subscriber_count == 1
        # Verbindungsende -> Abo abgebaut (kein Leak langlebiger Queues).
        assert bc.subscriber_count == 0

    asyncio.run(scenario())


def test_publish_without_subscribers_is_noop():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        # Darf nicht werfen (best-effort, NF-01): ein Alarm ohne Zuhoerer geht verloren
        # (Resync via DTB-31 deckt ab), bricht aber nie den Bewertungszyklus.
        bc.publish(_alarm(1))
        assert bc.subscriber_count == 0

    asyncio.run(scenario())


def test_publish_before_subscribe_is_not_replayed():
    # Scope-Grenze positiv abgesichert (broadcaster.py Docstring Z. 8-11, E-37): KEIN Replay-/
    # Last-N-Puffer. Ein VOR dem Abo publizierter Alarm wird einem spaeter verbundenen Client
    # NICHT nachgeliefert — der Resync laeuft ueber GET /v1/alarms (DTB-31), nicht ueber den
    # Stream. Pinnt die Abwesenheit jeder Historie: eine 'gut gemeinte' Replay-on-subscribe-
    # Regression (Nachlieferung bei Reconnect) liefe sonst durch alle Tests gruen und
    # kollidierte mit der DTB-31-Resync-Semantik (Doppelzustellung an G3).
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        bc.publish(_alarm(1))  # OHNE Abonnent -> darf nirgends gepuffert werden
        async with bc.subscribe() as queue:
            # Neu verbundener Client sieht keinen vor-Abo-Alarm (kein Replay).
            assert queue.empty()

    asyncio.run(scenario())


def test_publish_swallows_subscriber_error():
    # Best-effort (NF-01): wirft ein einzelner Abonnent beim Zustellen, darf publish NICHT
    # werfen (sonst wuerde ein kaputter Stream-Client den Bewertungszyklus reissen). Den
    # Fehler injizieren wir ueber die OEFFENTLICHE subscribe()-Naht (kein Privatzugriff auf
    # _subscribers): das put_nowait des realen Abo-Queues wirft.
    async def scenario() -> bool:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as queue:
            fired = {"x": False}

            def _boom(_item: object) -> None:
                fired["x"] = True
                raise RuntimeError("boom")

            queue.put_nowait = _boom  # type: ignore[method-assign]
            bc.publish(_alarm(1))  # darf nicht werfen
            return fired["x"]

    # Positiv belegen, dass der except-Swallow-Pfad (broadcaster.publish Z. 72-73) wirklich
    # durchlaufen wurde: ohne diesen Beweis bliebe der Test still vakuumig gruen, falls die
    # Zustellung von put_nowait auf z. B. `await queue.put` umgebaut wuerde (dann feuert _boom nie).
    assert asyncio.run(scenario()) is True


def test_publish_isolates_failing_subscriber_from_others(caplog):
    # Pro-Abonnent-Isolation (NF-01): wirft die Zustellung an EINEN Abonnenten, muessen ALLE
    # uebrigen den Alarm trotzdem erhalten. Das try/except sitzt PRO Queue im Loop, nicht um
    # die GANZE Schleife — eine Regression (try/except um die for, oder break/return statt
    # continue im Fehlerfall) liesse alle NACH dem werfenden Abo liegenden guten Abos
    # aushungern. Die Erkennung deterministisch machen (white-box, tests-only): publish
    # iteriert `for queue in self._subscribers`, das funktioniert auch ueber eine Liste ->
    # die Abo-Reihenfolge mit dem werfenden `bad` an Position 0 fixieren. So liegen ALLE
    # guten Abos garantiert NACH dem Fehler; die Zielregression wird in JEDEM Lauf rot
    # (nicht nur in ~5/6 wie bei instabiler set-Iteration).
    async def scenario() -> list[Alarm]:
        bc = AlarmBroadcaster()
        async with (
            bc.subscribe() as bad,
            bc.subscribe() as g1,
            bc.subscribe() as g2,
            bc.subscribe() as g3,
            bc.subscribe() as g4,
            bc.subscribe() as g5,
        ):
            gute = [g1, g2, g3, g4, g5]

            def _boom(_item: object) -> None:
                raise RuntimeError("boom")

            # `bad` ist das ZUERST verbundene Abo -> publish iteriert es zuerst (Zustellreihenfolge
            # = Abo-Reihenfolge, da _subscribers eine list ist). Alle guten Abos kommen danach;
            # die Zielregression (try/except um die GANZE Schleife statt pro Abo) greift sicher.
            bad.put_nowait = _boom  # type: ignore[method-assign]
            with caplog.at_level(logging.ERROR, logger="src.api.broadcaster"):
                bc.publish(_alarm(11))  # darf NICHT werfen (best-effort)
            # Kein Abo durch den Fehler verloren -> der kaputte Client reisst nichts ab.
            assert bc.subscriber_count == 6
            return [await asyncio.wait_for(q.get(), timeout=1) for q in gute]

    got = asyncio.run(scenario())
    # ALLE guten Abonnenten bekommen den Alarm trotz Fehler beim werfenden (Isolation belegt) —
    # das werfende Abo iteriert garantiert VOR allen guten, also greift die Regression sicher.
    assert [a.id for a in got] == [11, 11, 11, 11, 11]
    # Der Fehlerpfad wurde nachweislich durchlaufen (geloggt, nicht propagiert).
    assert any(
        record.levelno >= logging.ERROR and record.name == "src.api.broadcaster"
        for record in caplog.records
    )


def test_heartbeat_interval_matches_contract():
    # Contract: ~15 s Heartbeat. Pinnt den Default-Wert, damit eine Fehlkonfiguration
    # (z. B. 300 s) auffaellt — die uebrigen SSE-Tests setzen bewusst kleine heartbeat_s
    # und wuerden eine Drift am Default NICHT bemerken.
    assert _HEARTBEAT_S == 15.0
    # Zusaetzlich den TATSAECHLICH genutzten Default-Parameter pinnen, nicht nur die Konstante:
    # der Endpoint (v1.py) ruft sse_alarm_frames OHNE heartbeat_s und verlaesst sich voll auf
    # diesen Default. Wuerde er von _HEARTBEAT_S entkoppelt (z. B. heartbeat_s=30.0), liefe G2
    # mit falschem Heartbeat auf der eingefrorenen G2->G3-Naht, waehrend der Konstanten-Assert
    # oben gruen bliebe.
    assert inspect.signature(sse_alarm_frames).parameters["heartbeat_s"].default is _HEARTBEAT_S


def test_default_queue_is_bounded():
    # NF-01-Speichersicherheit am AUSGELIEFERTEN Default absichern: main.py verdrahtet
    # AlarmBroadcaster() OHNE max_queue, laeuft also voll auf _DEFAULT_MAX_QUEUE. Die Drop-
    # oldest-Tests setzen max_queue=2 explizit und wuerden eine Regression, die den Default
    # auf 0 (asyncio.Queue(maxsize=0) = UNBOUNDED) setzt, NICHT bemerken — dann waechst der
    # Puffer eines langsamen/haengenden SSE-Clients unbegrenzt (Resource-Exhaustion). Analog
    # zum Heartbeat-Default-Pin (test_heartbeat_interval_matches_contract).
    #
    # Bewusst KEIN == 100-Assert: die Puffergroesse ist internes Tuning, kein Wire-Contract.
    # Gepinnt wird nur die Invariante "endlich/bounded" (> 0, niemals 0 = unbounded).
    assert _DEFAULT_MAX_QUEUE > 0

    async def scenario() -> int:
        # Verhaltensbasiert: das real verdrahtete Default-Abo MUSS eine bounded Queue liefern.
        async with AlarmBroadcaster().subscribe() as queue:
            assert queue.maxsize == _DEFAULT_MAX_QUEUE
            assert queue.maxsize > 0  # 0 waere unbounded -> Speichersicherheit gebrochen
            return queue.maxsize

    assert asyncio.run(scenario()) == _DEFAULT_MAX_QUEUE


def test_publish_skips_and_logs_alarm_without_id(caplog):
    # Ingress-Guard (PR-Review): ein Alarm ohne DB-id (Bug: publish vor Persistenz) wird NICHT
    # gestreamt — best-effort verworfen + an der Quelle geloggt, statt "id: None" an ALLE Clients
    # zu verteilen. publish wirft dabei nicht (NF-01). _frame() haelt zusaetzlich als letzte Linie.
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as queue:
            with caplog.at_level(logging.ERROR, logger="src.api.broadcaster"):
                bc.publish(_alarm(1).model_copy(update={"id": None}))  # darf nicht werfen
            assert queue.empty()  # nichts zugestellt
        assert any("ohne DB-id" in record.getMessage() for record in caplog.records)

    asyncio.run(scenario())


def test_publish_drops_oldest_when_queue_full(caplog):
    async def scenario() -> list[int]:
        bc = AlarmBroadcaster(max_queue=2)
        async with bc.subscribe() as queue:
            # 3 Alarme ohne Konsum -> Puffer (2) laeuft ueber -> aeltester (id=1) faellt raus.
            with caplog.at_level(logging.WARNING, logger="src.api.broadcaster"):
                bc.publish(_alarm(1))
                bc.publish(_alarm(2))
                bc.publish(_alarm(3))
            first = await asyncio.wait_for(queue.get(), timeout=1)
            second = await asyncio.wait_for(queue.get(), timeout=1)
        return [first.id, second.id]

    got = asyncio.run(scenario())
    # Der NEUESTE Alarm ueberlebt (relevanteste Lage); der aelteste wird verworfen.
    assert got == [2, 3]
    # Der Drop MUSS die einzige Ops-/Resync-Spur fuer Datenverlust an der G2->G3-Naht
    # hinterlassen (NF-01-Observability, DTB-31): genau eine WARNING mit Verwerf-/Resync-Hinweis.
    # Faellt der logger.warning zu einem stillen Drop weg, wird dieser Test rot.
    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and record.name == "src.api.broadcaster"
    ]
    assert len(warnings) == 1
    assert "verworfen" in warnings[0].getMessage()
    assert "Resync" in warnings[0].getMessage()


def test_drop_oldest_is_isolated_per_queue_in_fan_out():
    # Fan-out + Backpressure kombiniert (broadcaster.py Docstring Z. 12-14): der Drop-oldest-
    # Zweig (Z. 63-71) wird sonst nur mit GENAU EINEM Abonnenten geprueft. Hier laufen ein
    # langsamer (nie konsumierender) und ein gesunder (sofort konsumierender) Abonnent parallel.
    # Der volle Puffer des langsamen Clients DARF dem gesunden keinen Alarm kosten: der Drop
    # ist pro Queue isoliert. Eine Regression mit break/return im if queue.full()-Block oder ein
    # Drop gegen das falsche/geteilte Queue liefe durch alle bestehenden (Einzel-Abo-)Tests
    # gruen, wuerde aber genau diesen Daseinszweck der bounded Queue brechen.
    #
    # WICHTIG zur Mechanik: publish() ist synchron (kein await zwischen den Abos), daher kann
    # der gesunde Client NICHT "leer bleiben und am Ende alle 3 holen" — bei max_queue=2 liefe
    # auch seine Queue ueber. Echte Isolation belegt nur, wer ZWISCHEN den publish-Aufrufen
    # konsumiert (genau das modelliert einen gesunden Client). `slow` ist das ZUERST verbundene
    # Abo -> publish iteriert es zuerst (Abo-Reihenfolge = list-Reihenfolge), damit eine
    # break/return-Regression den danach iterierten gesunden `fast` deterministisch um den
    # 3. Alarm braechte (sein fast.get() liefe sonst in den Timeout -> Test rot).
    async def scenario() -> list[int]:
        bc = AlarmBroadcaster(max_queue=2)
        async with bc.subscribe() as slow, bc.subscribe() as fast:
            bc.publish(_alarm(1))
            assert (await asyncio.wait_for(fast.get(), timeout=1)).id == 1
            bc.publish(_alarm(2))
            assert (await asyncio.wait_for(fast.get(), timeout=1)).id == 2
            # slow ist jetzt voll ([1, 2]) -> der 3. Alarm dropt slows aeltesten (id=1),
            # darf fast aber NICHT um id=3 bringen (Isolation).
            bc.publish(_alarm(3))
            assert (await asyncio.wait_for(fast.get(), timeout=1)).id == 3
            slow_ids = [
                (await asyncio.wait_for(slow.get(), timeout=1)).id for _ in range(slow.qsize())
            ]
        return slow_ids

    slow_ids = asyncio.run(scenario())
    # slow: aeltester (id=1) gedroppt, neueste ueberleben -> [2, 3]. fast hat oben bereits
    # lueckenlos [1, 2, 3] erhalten -> Backpressure des langsamen Clients ist pro Queue isoliert.
    assert slow_ids == [2, 3]


def test_reserve_rejects_new_abo_at_capacity():
    # Schutz gegen unbegrenzte gleichzeitige SSE-Verbindungen (Speicher-/Ressourcen-DoS):
    # ab max_subscribers lehnt reserve() ein weiteres Abo ab (StreamCapacityError) -> der
    # Endpoint kann das als 503 melden, statt den Broadcaster beliebig wachsen zu lassen.
    async def scenario() -> None:
        bc = AlarmBroadcaster(max_subscribers=2)
        bc.reserve()
        bc.reserve()
        assert bc.subscriber_count == 2
        with pytest.raises(StreamCapacityError):
            bc.reserve()  # 3. Verbindung -> abgelehnt

    asyncio.run(scenario())


def test_release_frees_capacity_for_new_abo():
    # Nach Verbindungsende (release) ist wieder Platz -> ein neuer Client darf abonnieren.
    # Pinnt, dass die Kapazitaet nicht dauerhaft "verbraucht" wird (sonst stuende der Stream
    # nach max_subscribers Reconnects bis zum Neustart fuer alle auf 503).
    async def scenario() -> None:
        bc = AlarmBroadcaster(max_subscribers=1)
        queue = bc.reserve()
        with pytest.raises(StreamCapacityError):
            bc.reserve()
        bc.release(queue)
        assert bc.subscriber_count == 0
        bc.reserve()  # wieder frei -> kein Fehler
        assert bc.subscriber_count == 1

    asyncio.run(scenario())


def test_subscribe_enforces_capacity_as_backstop():
    # subscribe() baut auf reserve()/release() auf -> setzt dieselbe Obergrenze durch und
    # raeumt das Abo am Verbindungsende wieder ab (Symmetrie zu den reserve/release-Tests).
    async def scenario() -> None:
        bc = AlarmBroadcaster(max_subscribers=1)
        async with bc.subscribe():
            assert bc.subscriber_count == 1
            with pytest.raises(StreamCapacityError):
                async with bc.subscribe():
                    pass
        assert bc.subscriber_count == 0  # erstes Abo nach Verlassen abgebaut

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# sse_alarm_frames — Contract-Frame-Formatierung
# ---------------------------------------------------------------------------


def test_frame_rejects_alarm_without_id():
    # Invarianten-Guard (PR-Review): nur persistierte Alarme (mit DB-id) duerfen gestreamt
    # werden. Ein Alarm mit id=None wuerde sonst "id: None" als SSE-Event-ID senden, die G3s
    # EventSource als Last-Event-ID speichert. raise (kein assert) -> -O-fest (Repo-Konvention).
    alarm_ohne_id = _alarm(1).model_copy(update={"id": None})
    with pytest.raises(ValueError, match="id"):
        _frame(alarm_ohne_id)


def test_sse_skips_malformed_alarm_and_keeps_stream_alive(caplog):
    # Resilienz (PR-Review MEDIUM): ein einzelner malformed Alarm (id=None, der publish() am
    # Ingress umgangen hat — z. B. direkter queue.put_nowait) darf den LIVE-Stream NICHT
    # abreissen. sse_alarm_frames ueberspringt ihn + loggt; die FOLGENDEN Alarme erreichen G3
    # weiter (NF-01-Geist: ein kaputtes Item kippt nicht den ganzen Feed). publish() + _frame()
    # bleiben die vorgelagerten Guards.
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(1).model_copy(update={"id": None}))  # malformed (umgeht publish)
        queue.put_nowait(_alarm(2))  # gueltig
        gen = sse_alarm_frames(queue, disconnect_after(2), heartbeat_s=5)
        return await _drain(gen)

    with caplog.at_level(logging.ERROR, logger="src.api.broadcaster"):
        frames = asyncio.run(scenario())
    # Nur der gueltige Alarm (id=2) wird zugestellt; der malformed wurde uebersprungen.
    assert len(frames) == 1
    assert frames[0].startswith("id: 2\n")
    assert any("malformed" in record.getMessage().lower() for record in caplog.records)


def test_sse_frame_carries_alarm_as_json_with_event_id():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(42, AlarmSeverity.CRITICAL))
        gen = sse_alarm_frames(queue, disconnect_after(1), heartbeat_s=5)
        return await _drain(gen)

    frames = asyncio.run(scenario())
    assert len(frames) == 1
    frame = frames[0]
    # `id:` = Alarm-ID (Reconnect via Last-Event-ID), `data:` = Alarm-JSON, Leerzeile = Event-Ende.
    assert frame.startswith("id: 42\n")
    assert "data: " in frame
    assert frame.endswith("\n\n")
    # Wire-Form-Guard: die `data:`-Nutzlast IST die eingefrorene G2->G3-Naht (E-37). Das
    # vollstaendige Alarm-Schema pinnen — sonst leakt ein neues internes Pydantic-Feld
    # (z. B. cleared_at) ungeprueft auf den Stream, und ein Wegfall/Aliasing von
    # assessment_id/raised_at wuerde G3 brechen, ohne dass ein Test rot wird.
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line[len("data: ") :])
    assert set(payload) == {"id", "assessment_id", "severity", "raised_at", "state"}
    assert payload["id"] == 42
    assert payload["assessment_id"] == 420  # alarm_id * 10
    assert payload["severity"] == "critical"
    assert payload["state"] == "active"
    # UTC-Instant verifizieren (nicht ein hartkodiertes Format-Literal): ein geaendertes
    # datetime-Format auf der Naht wuerde G3 brechen.
    assert datetime.fromisoformat(payload["raised_at"].replace("Z", "+00:00")) == _T0


def test_sse_emits_heartbeat_on_idle():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()  # leer -> Timeout -> Heartbeat
        gen = sse_alarm_frames(queue, disconnect_after(1), heartbeat_s=0.01)
        return await _drain(gen)

    frames = asyncio.run(scenario())
    # SSE-Kommentarzeile, damit G3 einen still gestorbenen Stream von einem ruhigen unterscheidet.
    assert frames == [":keep-alive\n\n"]


def test_sse_stops_immediately_when_already_disconnected():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(1))
        gen = sse_alarm_frames(queue, disconnect_after(0), heartbeat_s=5)  # sofort getrennt
        return await _drain(gen)

    frames = asyncio.run(scenario())
    assert frames == []  # getrennter Client -> kein Frame, sauberer Abbruch


def test_sse_emits_consecutive_alarms_in_event_id_order():
    # Steady-State-Schleife: MEHRERE Alarme hintereinander muessen alle in `id:`-Reihenfolge
    # rausgehen. Eine Regression, die die Schleife nach dem ersten Output verlaesst (return/break
    # statt continue), bliebe sonst gruen — G3 erhielte im Dauerbetrieb nur das erste Event.
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(1))
        queue.put_nowait(_alarm(2))
        gen = sse_alarm_frames(queue, disconnect_after(2), heartbeat_s=5)
        return await _drain(gen)

    frames = asyncio.run(scenario())
    assert len(frames) == 2
    assert frames[0].startswith("id: 1\n")
    assert frames[1].startswith("id: 2\n")


def test_sse_continues_with_alarm_after_heartbeat():
    # Interleave Heartbeat -> dann Alarm: nach einem Leerlauf-Heartbeat (continue nach
    # TimeoutError) MUSS die Schleife weiterlaufen und einen danach eintreffenden Alarm noch
    # zustellen. Verankert die continue-Fortsetzung, die die disconnect_after(1)-Tests nicht
    # treffen (jeder dort beendet nach genau einem Output).
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()  # leer -> erste Runde Heartbeat
        gen = sse_alarm_frames(queue, disconnect_after(2), heartbeat_s=0.01)
        first = await gen.__anext__()  # Leerlauf -> Heartbeat
        queue.put_nowait(_alarm(8))  # jetzt Alarm einreihen
        second = await gen.__anext__()  # Schleife setzt nach continue fort -> Alarm-Frame
        await gen.aclose()
        return [first, second]

    frames = asyncio.run(scenario())
    assert frames[0] == ":keep-alive\n\n"
    assert frames[1].startswith("id: 8\n")
