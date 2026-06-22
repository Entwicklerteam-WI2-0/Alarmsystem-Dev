# Persönliches Entscheidungslog — Lucas Vöhringer (G2)
> **Erstellt am:** 2026-06-22 · **Letzte Bearbeitung:** 2026-06-22
> **Autor:** Lucas Vöhringer (Systemarchitekt) · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).
> Persönliches Log (Einzelleistung). Das zentrale Architektur-Logbuch des Teams ist
> `Entscheidungslog-Lucas-Systemarchitektur.md` (ADR-Format E-xx); je Eintrag steht der Querverweis dorthin.

---

## 2026-06-22 — G1-Datennaht auf Pull umgestellt (Snapshot-Abruf statt Push)
- **Kontext/Task:** P1.3 Seam-Sync mit G1 · E-02/E-04/E-06 (API+Datenmodell = einzige Naht, G2-Verantwortung, contract-first) · FA Schnittstellen · NF-01 (Fail-safe). Zentrales Log: **E-31** (löst E-30 ab).
- **Entscheidung:** Die Sensor→Backend-Naht läuft als **Pull**. G1 stellt `GET /current` bereit — alle aktuellen Messwerte als **einen** Snapshot mit **einem** gemeinsamen Mess-Zeitstempel (`measured_at`) — plus `GET /health`. G2 baut einen Poller/HTTP-Client, der in einem **selbst bestimmten** Intervall (≤ 60 s) abruft, validiert und persistiert. Kein von G2 gehosteter `POST /readings`-Endpoint mehr.
- **Begründung:** Ursprünglich war für die Naht das Push-Modell empfohlen (G1 sendet an einen von G2 gehosteten POST-Endpoint). Im realen Seam-Sync hat G1 jedoch bestätigt, einen **abfragbaren** Endpoint bereitzustellen, statt aktiv zu pushen. Damit ist die zentrale Annahme des Push-Modells — G1-Hardware könne keinen dauerverfügbaren, abfragbaren Dienst bereitstellen — widerlegt; eine einseitig gegen einen Pull-bauenden Partner diktierte Push-Naht wäre nicht umsetzbar gewesen. Pull hat zudem strukturelle Vorteile: Das Frontend (G3) fragt das Backend ohnehin per GET ab, sodass Pull an der G1-Seite ein **einheitliches Request/Response-Modell** über alle Nahtstellen ergibt statt zweier gegenläufiger Richtungen. Die Fail-safe-Anforderung (NF-01) bleibt erfüllbar, indem **Erreichbarkeit** (`GET /health` bzw. Timeout) **getrennt** von **Datenaktualität** (`measured_at` zu alt → stale) geprüft wird — beide Signale liefert G1. Außerdem bestimmt G2 so das Abrufintervall und die Stale-Grenze selbst, statt vom Sende-Takt von G1 abzuhängen. Bewusst gewählt wurde ein **Snapshot**-Endpoint (alle Werte + ein gemeinsamer `measured_at`) statt getrennter Einzel-Endpoints, weil die Bewertungslogik `T_s`, `ΔT` und `RH` aus **demselben Messmoment** braucht; getrennte Abrufe würden Werte aus verschiedenen Zeitpunkten mischen und die 4-Stufen-Logik verfälschen.
- **Alternativen (erwogen/verworfen):**
  - *Push (`POST /readings`, G2 hostet den Endpoint):* ursprünglich empfohlen, durch die G1-Realität überholt — G1 stellt einen Abfrage-Endpoint bereit, hostet keinen Sender.
  - *Pull mit getrennten Einzel-Endpoints je Messgröße:* verworfen — „gleichzeitiger Abruf" garantiert keinen gemeinsamen Mess-Zeitpunkt; die Bewertung würde inkonsistente Snapshots mischen. Stattdessen **ein** Snapshot mit gemeinsamem `measured_at`.
- **Bewusster Tradeoff:** An der G1-Naht ist G2 nun **Client** (G1 definiert den Endpoint-Shape); Datenmodell und die G3-API bleiben in G2-Hoheit.
- **Ergebnis/Status:** umgesetzt + dokumentiert (Backend-Konzept §1/§2/§3/§9, Faktenblatt). Contract-Detail (Feldnamen/Einheiten) mit G1 im Seam-Sync final, mit **P1.4** einzufrieren. PR #32 gemergt.

## 2026-06-22 — Niederschlag als Bewertungsfaktor gestrichen → 3-Faktor-Bewertung
- **Kontext/Task:** Customer-/Product-Owner-Entscheid · präzisiert die Bewertungslogik · FA Risikobewertung · `Schwellenwerte.md §2`. Zentrales Log: **E-32**.
- **Entscheidung:** Niederschlag entfällt als vierter Bewertungsfaktor **und** als Datenfeld `precip_type`. Die Vereisungsbewertung läuft auf **drei Faktoren**: Oberflächentemperatur `T_s` + Taupunkt-Abstand `ΔT` + Feuchte `RH`.
- **Begründung:** Der Kunde verantwortet den Funktionsumfang und benötigt die Niederschlagsart nicht; ohne Bedarf und ohne vorgesehenen Sensor-Feed entfällt der Faktor. Die Mindestanforderungen bleiben erfüllt, weil beide dokumentierten Vorfälle nie an Niederschlag hingen: Vorfall 1 (−2,1 °C, trockene Oberfläche) löst über fehlende Oberflächenfeuchte zu GELB auf, Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C, Reif) über `T_s` und `ΔT ≤ 0` zu ROT. Die Schwellenwerte selbst bleiben unberührt; reduziert wird nur die **Struktur** der Regel (ROT verliert den „gefrierender Niederschlag"-Trigger, die „Feuchte vorhanden"-Definition den Niederschlags-Term).
- **Bewusste Konsequenz (ehrlich):** Aktiver gefrierender Regen bei `T_s` knapp über 0 °C lässt sich ohne Niederschlagssensor nicht mehr als **eigenes** Signal erkennen — nur noch indirekt über `T_s`/`ΔT`. Das ist mit dem Wegfall des Faktors bewusst in Kauf genommen (Customer-Entscheid).
- **Alternativen (erwogen/verworfen):**
  - *Niederschlag behalten:* gegen den Customer-Scope; kein Bedarf, kein Sensor-Feed vorgesehen.
  - *Niederschlag durch einen Proxy herleiten (aus `RH`/`ΔT`):* verworfen — spekulativ, ohne Anforderung; würde Scheingenauigkeit vortäuschen.
- **Ergebnis/Status:** umgesetzt (`Schwellenwerte.md §1–§4`, `Backend-Konzept.md §4/§5/§10`, Datenmodell ohne `precip_type`). PR #32 gemergt.

## 2026-06-22 — Feuchte-Kriterium an die Oberfläche gebunden (`ΔT` statt Luft-RH)
- **Kontext/Task:** Review-Befund bei der 3-Faktor-Umstellung · FA-01 (Oberflächenfeuchte) · K1 (Fehlalarm-Vermeidung) · NF-01 · `Schwellenwerte.md §2`. Zentrales Log: **E-33**.
- **Entscheidung:** „Feuchte vorhanden" wird an die **Oberfläche** gebunden: `„Feuchte vorhanden" := ΔT (T_s − T_d) ≤ 1,0 °C`. Der frühere Term `RH ≥ 90 %` (Luftfeuchte) wird gestrichen.
- **Begründung:** Bei der Umstellung fiel auf, dass die „Feuchte vorhanden"-Regel den Luftfeuchte-Term `RH ≥ 90 %` enthielt, während `RH` als **Luft**feuchte definiert ist. Vorfall 1 — der zu vermeidende Fehlalarm — hat **92 % Luftfeuchte bei trockener Oberfläche**. Mit dem alten Term hätte die Logik Vorfall 1 als ORANGE klassifiziert und damit genau den Fehlalarm reproduziert, dessen Vermeidung das Designziel ist. Luftfeuchte sagt nichts über den Zustand der Oberfläche aus; FA-01 nennt ausdrücklich die **Oberflächenfeuchte** als Entscheidungsgröße. Der Taupunkt-Abstand `ΔT` (Oberflächentemperatur minus Taupunkt) ist der physikalisch korrekte Indikator dafür, ob sich an der Oberfläche real Feuchte niederschlägt — und er kommt **ohne zusätzlichen Sensor** aus, weil er aus den ohnehin vorhandenen Größen berechnet wird (Lufttemperatur und Luftfeuchte fließen über den Taupunkt `T_d` weiter indirekt ein). Mit der Korrektur löst Vorfall 1 zu GELB auf (`ΔT > 1,0`), Vorfall 2 weiterhin zu ROT (`ΔT ≤ 0`).
- **Alternativen (erwogen/verworfen):**
  - *Separater Oberflächenfeuchte-Sensor:* verworfen — unnötig, `ΔT` genügt; zusätzliche Kosten und Sensorabhängigkeit.
  - *`RH ≥ 90 %` belassen:* verworfen — reproduziert den Fehlalarm, verfehlt das Designziel (K1).
- **Konsequenz für die G1-Naht:** `humidity_pct` im `GET /current`-Snapshot ist als **Luft**feuchte ausreichend (Input für `T_d`); ein separater Oberflächenfeuchte-Wert ist nicht erforderlich. Im Seam-Sync klarstellen, dass `humidity_pct` = Luftfeuchte.
- **Ergebnis/Status:** umgesetzt (`Schwellenwerte.md §1/§2/§4`). Schwellen bleiben parametrierbare Dummies (G1-Finalwerte ausstehend, NF-05). PR #32 gemergt.
