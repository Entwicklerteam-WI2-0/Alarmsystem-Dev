---
marp: true
theme: default
paginate: true
size: 16:9
header: 'G2 — Backend & Entscheidungslogik · Vereisungserkennung ANR'
footer: 'Abschlusspräsentation M3 · 02.07.2026'
---

<!--
SPRECHER-LEITFADEN (nicht projizieren — siehe 00-Struktur-und-Sprecher-Leitfaden.md):
- Hauptsprecher durchgehend: LUCAS (Systemarchitekt).
- Übergabe Folie 18: JOHANNES (Edge Cases + Testsuite), ~3 min.
- Übergabe Folie 20: ANDI (Betrieb / Raspberry-Pi), ~2 min.
- Presenter-Notes stehen je Folie als HTML-Kommentar. In Marp: Presenter-View zeigt sie an.
- Kriterien-Tags (①–⑥) unten je Folie sind für die Dozenten, nicht vorlesen.
- PDF-Export: marp 01-backend-deck.md --pdf --allow-local-files
-->

# Vereisungserkennung am Flughafen ANR
## Gruppe 2 — Backend & Entscheidungslogik

**Wie aus widersprüchlichem Chaos ein fail-safe Entscheidungssystem wurde**

Systemarchitektur & Vortrag: **Lucas Vöhringer**
Fach-Einschübe: **Johannes Petzold** (Tests & Edge Cases) · **Andreas Moritz** (Betrieb)

*Abschlusspräsentation · Woche 3 · 02.07.2026*

<!--
Einstieg (30 s): "Wir sind Gruppe 2 — das Backend. Zwischen den Sensoren von G1 und der Anzeige
von G3 sitzt unsere Entscheidungslogik: die Frage, ob die Startbahn vereist ist oder nicht.
Ich nehme euch mit von einem chaotischen Briefing bis zu einem System, das genau die zwei
realen Fehler nicht mehr macht, an denen ANR gescheitert ist."
Selbstbewusst, ruhig starten. Nicht entschuldigen, nicht relativieren.
-->

---

## Agenda — unser roter Faden

1. **Das Chaos** — zwei reale Vorfälle, ein widersprüchliches Briefing
2. **Die Erkenntnis** — warum Lufttemperatur lügt
3. **Die Weichen** — unsere vier Schlüsselentscheidungen
4. **Das System** — Datenmodell, API, Bewertung, Fail-safe
5. **Der Beweis** — Live-Demo
6. **Team & Methode** — wie wir organisiert waren
7. **Ehrliche Reflexion** — was wir gelernt haben

<!--
15 s. "Kein Katalog von Features — eine Geschichte. Am Ende wisst ihr, warum das System so
aussieht, wie es aussieht." Agenda nicht vorlesen, nur als Landkarte zeigen.
-->

---

<!-- _class: lead -->
# 1 · Das Chaos
### Zwei Vorfälle. Ein Briefing ohne Spezifikation.

---

## Der Auftrag

**Flughafen ANR** — Regionalflughafen in Mittelgebirgslage. In den letzten Wintern:

- ❄️ nicht erkannte Vereisungen
- 🚫 unnötige Startbahn-Sperrungen
- 💸 hohe Betriebskosten & unklare Entscheidungsgrundlagen

**Unsere Rolle:** externes Ingenieurteam. **G2 baut die Entscheidungslogik** — das Gehirn
zwischen Sensor (G1) und Anzeige (G3).

> Es gibt **keine** fertige Spezifikation. Das Lastenheft mussten wir aus dem Material erst herleiten.

<sub>① Umgang mit widersprüchlichen Anforderungen</sub>

<!--
1 min. Betonung auf "keine Spezifikation" — das ist der Kern der Aufgabe und der Bewertung.
Nicht als Problem framen, sondern als das eigentliche Engineering: aus Chaos Ordnung machen.
-->

---

## Die zwei realen Vorfälle

| | Situation | Reine Lufttemperatur sagt | Realität |
|---|---|---|---|
| **①** | Luft **−2,1 °C**, trockene Oberfläche | 🔴 Alarm! | ✅ **kein Eis** → Fehlalarm |
| **②** | Luft **+1,2 °C**, Oberfläche unter 0 °C | 🟢 alles gut | ❄️ **Eisbildung** → übersehen |

**Beide Fehler haben dieselbe Wurzel:** die Lufttemperatur allein ist die falsche Messgröße.

Das ist der Ausgangspunkt für unsere gesamte Bewertungslogik.

<sub>① Umgang mit widersprüchlichen Anforderungen · ③ Datenanalyse</sub>

<!--
1,5 min. DAS ist die stärkste Folie der ganzen Präsi. Langsam sprechen. Erst Vorfall 1, dann 2.
"Ein System, das nur die Luft misst, macht BEIDE Fehler. Ein Fehlalarm kostet Geld — eine
übersehene Vereisung kostet ein Flugzeug." Diese Vorfälle kommen in Akt 2 als Auflösung zurück.
-->

---

## Das Rohmaterial: unvollständig & widersprüchlich

Wir bekamen **keine** Anforderungen, sondern:

- 📧 interne E-Mails · 💬 Chatverläufe · 📝 Meetingprotokolle · 🗒️ technische Notizen

Daraus haben wir ein **versioniertes Lastenheft** destilliert:

- **FA-01…12** funktionale Anforderungen · **NF-01…11** nicht-funktionale
- **RB-01** harte Randbedingung · **K1–K9** dokumentierte Zielkonflikte

> Widersprüche haben wir **nicht wegoptimiert**, sondern als offene Entscheidungen markiert und
> dem Team vorgelegt.

<sub>① Umgang mit widersprüchlichen Anforderungen</sub>

<!--
1,5 min. Zeig, dass ihr methodisch vorgegangen seid: aus Chaos → strukturierte IDs.
K1 (Fehlalarm vs. Auslassung) hier kurz nennen — kommt in Reflexion wieder.
RB-01 kurz anteasern: "eine Regel war heilig — dazu gleich mehr."
-->

---

<!-- _class: lead -->
# 2 · Die Erkenntnis
### Warum Lufttemperatur lügt — und was wir stattdessen messen

---

## Die Lösung: drei Faktoren statt einem

Nicht die Luft entscheidet, sondern die **Oberfläche**:

| Faktor | Größe | Rolle |
|---|---|---|
| 🌡️ **Oberflächentemperatur** `T_s` | gemessen (DS18B20) | **primäre** Entscheidungsgröße |
| 💧 **Taupunkt** `T_d` | berechnet (Magnus aus Luft + Feuchte) | Kondensations-Referenz |
| 📏 **Taupunkt-Abstand** `ΔT = T_s − T_d` | abgeleitet | „ist die Oberfläche feucht?" |

Lufttemperatur `T_a` bleibt nur **Kontext** — nie Entscheidungsfaktor.

<sub>③ Qualität der Datenanalyse</sub>

<!--
2 min. Magnus-Konstanten (a=17,62 · b=243,12) nur nennen, wenn gefragt (Backup-Folie B2).
Kernsatz: "Eine warme Luft über einer kalten Oberfläche — das ist genau der Fall, den die
Luftmessung nicht sieht. Deshalb messen wir die Oberfläche direkt."
-->

---

## Und so lösen sich beide Vorfälle auf

| Vorfall | 3-Faktor-Bewertung | Ergebnis |
|---|---|---|
| **①** Luft −2,1 °C, **trocken** | `T_s ≤ 0` **aber** `ΔT > 1,0` → keine Oberflächenfeuchte | 🟡 GELB, **kein Alarm** ✅ |
| **②** Luft +1,2 °C, Oberfläche < 0 °C | über `T_s < 0` erfasst | 🟠 ORANGE / 🔴 ROT ✅ |

**Sicherheits-Bias (K1):** verpasste Vereisung = 0 % Ziel > Fehlalarm < 1 % Ziel.
→ *„Lieber zehn Fehlalarme als ein vereistes Flugzeug."*

<sub>③ Datenanalyse · ① widersprüchliche Anforderungen</sub>

<!--
1,5 min. Der Payoff der Vorfall-Folie aus Akt 1. "Erinnert ihr euch an die zwei Fehler?
Mit drei Faktoren macht das System keinen davon mehr." Das ist der emotionale Höhepunkt der
Datenanalyse. Kurz innehalten nach dieser Folie.
-->

---

## Datenbasis & Kalibrierung — ehrlich

- Sensoren aus **realen Datenblättern** ausgewählt: DS18B20 (Oberfläche), BME280 (Luft/Feuchte),
  STEMMA-Soil (Oberflächenfeuchte)
- Standort-Annahme: **ANR ≈ Flugplatz Coburg** (dokumentierte Annahme, kein Briefing)
- Schwellen aus Datenblättern abgeleitet + an Standort plausibilisiert

> **Grenze offen benannt:** messtechnische Endkalibrierung steht aus (ein Sensor defekt, einer
> nicht kalibrierbar). Deshalb sind **alle** Schwellen parametrierbar (NF-05) — kein Hardcode.

<sub>③ Qualität der Datenanalyse · ⑥ Reflexion</sub>

<!--
1 min. Ehrlichkeit punktet bei den Dozenten. Nicht so tun, als sei alles fertig kalibriert —
sondern: wir kennen die Grenze und haben sie architektonisch abgefangen (parametrierbar).
-->

---

<!-- _class: lead -->
# 3 · Die Weichen
### Vier Entscheidungen, die alles geprägt haben

---

## Vier Schlüsselentscheidungen auf einen Blick

| # | Entscheidung | Kern |
|---|---|---|
| **E-29** | **MySQL/MariaDB** als Datenbank | Vorgabe von oben — kritisch geprüft, angenommen |
| **E-31** | **Pull statt Push** an der G1-Naht | „Realität schlägt Empfehlung" |
| **E-35** | **rohes PyMySQL, kein ORM/Docker** | bewusst einfach fürs 3-Wochen-Team |
| **E-40** | **Fail-safe in 6 Schichten** | nie GRÜN bei Ausfall — Default, kein Sonderfall |

Jede mit dokumentierten Alternativen im Entscheidungslogbuch (>300 KB, nachvollziehbar).

<sub>② Nachvollziehbarkeit technischer Entscheidungen</sub>

<!--
30 s. Nur Überblick — die nächsten drei Folien vertiefen. "Alle vier sind im Logbuch mit
Alternativen und Begründung dokumentiert — das ist die Nachvollziehbarkeit, die bewertet wird."
-->

---

## E-29 · MySQL — eine Vorgabe von oben

**Die Geschäftsleitung diktierte:** „Speicherung auf Basis einer MySQL-Datenbank."
Begründung: vorhandene Kompetenz, etablierte Backup-Prozesse, Wartbarkeit > neue Technologie.

**Unser Auftrag war nicht Gehorsam, sondern kritische Prüfung (§6a):**

- ✅ geprüft: SQLite durchgängig, SQLite-dev + MySQL-prod, PostgreSQL/TimescaleDB
- ✅ Ergebnis: **kein schwerwiegender technischer Gegengrund** für die Prototyp-Last
- ✅ Entscheidung: Vorgabe **angenommen** — *eine* DB durchgängig vermeidet teuren Dialekt-Drift

> Genau das wollten die Dozenten sehen: eine Anforderung nicht abnicken, sondern **belegt bewerten**.

<sub>① widersprüchliche Anforderungen · ② Nachvollziehbarkeit</sub>

<!--
2 min. DIESE Folie ist Gold fürs Kriterium "Umgang mit Anforderungen". Erzähl es als Konflikt:
"Ein Stakeholder gibt etwas vor — wir hätten dagegen argumentieren können. Haben wir geprüft.
Und dann eine erwachsene Entscheidung getroffen: die Vorgabe war technisch tragfähig, also
haben wir sie angenommen — mit Beleg, nicht aus Bequemlichkeit."
-->

---

## E-31 · Push → Pull: Realität schlägt Empfehlung

**Zuerst empfahl ich Push** (E-30): G1 schickt Messwerte aktiv an uns.

**Dann der reale Team-Sync:** G1 baut faktisch einen **Abfrage-Endpoint**. Die Annahme hinter
E-30 war widerlegt.

**Also revidiert (E-31):** G2 **pollt** G1 — `GET /current` + `GET /health`, alle 30 s.

- einheitliches Modell: G3 pollt G2, G2 pollt G1
- Fail-safe bleibt: Erreichbarkeit (`/health`) **getrennt** von Datenaktualität (`measured_at`)

> Lernmoment: eine Empfehlung ist eine **Hypothese** — sie muss gegen die Team-Realität bestehen.

<sub>② Nachvollziehbarkeit · ⑥ Reflexion</sub>

<!--
2 min. Zeig Reife: du hast deine eigene Empfehlung verworfen, als die Realität sie widerlegte.
"Ich hätte auf Push bestehen können — gegen einen Partner, der Pull baut. Das wäre Sturheit
gewesen, kein Engineering." Das ist ein starkes persönliches Reflexionssignal (40%).
-->

---

## E-35 · Bewusst einfach: kein ORM, kein Docker

Für **sechs simple Tabellen** wäre ein schweres Setup Overkill:

| Verworfen | Warum |
|---|---|
| SQLAlchemy ORM / Core | Overkill + Lernkurve für ein 2.-Semester-Team |
| Alembic-Migrationen | unnötig bei stabilem, handgeschriebenem `schema.sql` |
| Docker-Compose-MariaDB | Einstiegshürde ohne Mehrwert — native MariaDB läuft schon |

**Gewählt:** rohes **PyMySQL** + parametrisierte Queries (Pflicht) + Repository-Pattern.

> Preis, den wir kennen: Schema-Änderungen manuell; Injection-Schutz per Disziplin + Review.

<sub>② Nachvollziehbarkeit</sub>

<!--
1,5 min. Botschaft: gute Architektur heißt WEGLASSEN. "Wir haben uns bewusst gegen die
'erwachsene' Lösung entschieden, weil sie zum Team und zur Aufgabe nicht passt. YAGNI."
Den Trade-off offen nennen zeigt, dass ihr ihn verstanden habt.
-->

---

<!-- _class: lead -->
# 4 · Das System
### Datenmodell · API · Bewertung · Fail-safe

---

## Architektur — zwei Nähte, beide in G2-Hoheit

```
   G1 — Sensorik              G2 — Backend (wir)              G3 — Frontend
  ┌─────────────┐         ┌──────────────────────┐         ┌──────────────┐
  │ Hardware    │  Pull   │ Ingest → Validierung  │  REST   │ Ampel        │
  │ GET /current│ ──30s─► │ → Bewertung → API     │ ──+SSE► │ Alarme       │
  │ GET /health │         │ → Alarme → Persistenz │         │ Historie     │
  └─────────────┘         └──────────┬───────────┘         └──────────────┘
                                     ▼
                          MariaDB / MySQL (schema.sql)
```

**Kritischer Pfad:** Ingest → Validierung/Fail-safe → Persistenz → **Bewertung** → API → Alarm → Ack

<sub>④ technische Umsetzung</sub>

<!--
1,5 min. Der ASCII-Flow rendert IMMER (beamer-safe). Optional: das schöne Mermaid-PNG aus
Architekturdiagramm.md hier einsetzen (Datei nach assets/architektur.png exportieren, dann
![](assets/architektur.png) statt dem Codeblock). Mermaid-Quelle liegt in Backup-Folie B4.
Kernsatz: "Wir sind Client zu G1 und Server zu G3 — beide Nähte definieren wir."
-->

---

## Datenmodell — 6 Entitäten

| Tabelle | Zweck |
|---|---|
| `threshold_set` | versionierter, parametrierbarer Schwellensatz (NF-05) |
| `reading` | Messwert-Snapshot (G1-Felder + berechneter Taupunkt) |
| `assessment` | Bewertungsergebnis — audit-fester Entscheidungs-Snapshot |
| `alarm` | aus Bewertung erzeugter Alarm (**kein Aktor** — RB-01) |
| `acknowledgement` | Operator-Quittierung (append-only, NF-09) |
| `audit_log` | lückenloses Ereignis-Log (append-only, NF-09) |

Handgeschriebenes `schema.sql`, MariaDB, alle Zeitstempel UTC.

<sub>④ technische Umsetzung</sub>

<!--
1 min. RB-01 hier betonen: "Der Alarm ist ein Signal an einen Menschen — niemals ein Aktor,
der die Startbahn selbst sperrt. Die Verantwortung bleibt beim Menschen." Sicherheitskritische
Grundregel. audit_log = alles nachvollziehbar (NF-09).
-->

---

## Die API — eingefroren als v1.0

**Konsumiert von G1 (wir pollen):** `GET /current` · `GET /health`

**Bereitgestellt für G3 (wir sind Server, alle `/v1/`):**

| Endpoint | Zweck |
|---|---|
| `GET /v1/assessment/current` | Ampel + Roh-Messwerte (flach) |
| `GET /v1/alarms/stream` | **SSE** — Live-Push von Alarmen |
| `GET /v1/alarms` · `POST /v1/alarms/{id}/ack` | Resync · Quittierung |
| `GET /v1/readings` · `GET /v1/audit` | Historie · Audit-Log |
| `GET`/`POST /v1/thresholds` | Schwellen lesen / versioniert setzen (Auth) |

> **Contract-first eingefroren** → G1 und G3 konnten **parallel** gegen die Spec bauen.

<sub>④ technische Umsetzung · ⑤ Teamorganisation</sub>

<!--
1,5 min. Der Freeze ist das strategische Herzstück: "Diese eine Naht früh einzufrieren hat
G1 und G3 gleichzeitig entblockt — niemand musste auf unser fertiges Backend warten."
3 Design-Abwägungen kurz: Pull (E-31), flaches Format ohne Metadaten-Hülle (E-36), SSE-Push (E-37).
Bei Detailfragen: Backup / openapi.yaml.
-->

---

## Die 4-Stufen-Kaskade

Geprüft **von der gefährlichsten Stufe abwärts** — die erste zutreffende gewinnt:

| Stufe | Bedingung | Alarm |
|---|---|---|
| 🔴 **ROT** | `T_s ≤ 0 °C` **und** `ΔT ≤ 0` | CRITICAL |
| 🟠 **ORANGE** | `T_s ≤ 0 °C` **und** Feuchte (`ΔT ≤ 1,0`) | WARNING |
| 🟡 **GELB** | `T_s ≤ +1,0 °C` **oder** Prognose ≤ 0 °C in 30 min | — |
| 🟢 **GRÜN** | `T_s > +1,0 °C` und Taupunkt bekannt | — |

Alle Schwellen aus `config/thresholds.json` — **kein einziger Zahlenliteral** im Code (NF-05).

<sub>④ technische Umsetzung</sub>

<!--
1 min. GELB hat eine Prognose-Komponente (30-min-Vorlauf, FA-06) — Fluglotsen brauchen Vorlaufzeit.
"Die Stufen überlappen bewusst — jeder ROT-Fall erfüllt auch ORANGE. Die Reihenfolge garantiert
immer die höchste zutreffende Stufe." Betonen: parametrierbar, nicht hardcoded.
-->

---

## Fail-safe (NF-01) — nie GRÜN bei Ausfall

**Der sichere Zustand ist der Default, kein Sonderfall.** GRÜN nur, wenn **alle 6 Schichten** ok:

1. **Ingest/Stale** — Daten älter als 120 s → `unknown`
2. **Sensor-Fault** — Status `fault` → `unknown`
3. **Plausibilität** — Sprung > 5 °C/min, Flatline (15 min, ≤ 0,15 °C), NaN/inf → verworfen
4. **DB-Ausfall** — HTTP 503 + `unknown` (kein Crash)
5. **Bewertungs-Kaskade** — fehlender Taupunkt → konservativ, nie GRÜN
6. **Serve-Zeit-Re-Check** — Daten dürfen zwischen Bewertung und Abruf altern

<sub>④ technische Umsetzung</sub>

<!--
1,5 min. Das ist der sicherheitskritische Kern. "Ein einzelner Check ist fragil — die DB kann
weg sein, während die Bewertung gut ist. Deshalb Defense-in-depth über sechs Schichten."
Überleitung zu Johannes: "Aber ein Fail-safe ist nur so gut wie die Fälle, gegen die es
getestet wurde. Johannes hat das System gebrochen, bevor es der Winter tut."
-->

---

## [ Johannes ] Edge Cases & Testsuite

**Adversarial getestet — das System aktiv zu brechen versucht:**

- 🐛 **NaN-Guard (DTB-38):** `assess_ice_risk(NaN, …)` lieferte still **GRÜN** — in einem
  sicherheitskritischen System ein **Blocker**. Gefunden, gefixt, als Test verankert.
- 🔁 **Flatline-Escape (Santa-Loop, DTB-20):** klemmender Sensor als CRITICAL entlarvt.
- 🧪 **Demo-Feed gegen die echte Kaskade** getestet — Preset-Bugs (falsch GRÜN/GELB) gefunden.

> **Methodische Erkenntnis:** *„Tests grün ≠ Produkt läuft."* Der scharfe Live-Lauf zeigte, was
> die grüne Suite nicht sah.

<sub>④ technische Umsetzung · ⑥ Reflexion</sub>

<!--
JOHANNES spricht (~3 min). Deine Stärke: Edge Cases + Testsuite + adversariales Testen.
Erzähl den NaN-Fund als Story: ein plausibel aussehender Wert, der still die gefährlichste
Falschaussage produziert. "Solche Lücken findet man nicht durch Nachdenken — nur durch
gezieltes Brechen." Zurück an Lucas: "…und jetzt sehen wir, dass es live funktioniert."
-->

---

<!-- _class: lead -->
# 5 · Der Beweis
### Live-Demo

---

## Live-Demo — das System bei der Arbeit

Wir fahren die Ampel **live** durch die volle Kaskade:

🟢 grün → 🟡 gelb → 🟠 orange **+ Alarm** → 🔴 rot **+ CRITICAL** → **Ack** → ⚠️ fault/stale → 🟢 recovery

- **Self-checking:** jeder Schritt wird live gegen die `/v1`-API geprüft (`PASS`/`FAIL`)
- **Fail-safe live provoziert:** Sensor auf `fault` → Ampel wird `unknown`, **nie GRÜN**

> Falls die Technik streikt: Backup-Screenshots am Ende (`ALLE N PASS`).

<sub>④ technische Umsetzung (Live-Demo)</sub>

<!--
LUCAS fährt die Demo (~6 min, bereits konzipiert — Drehbuch im bestehenden Demo-Konzept).
Ruhig, ein Szenario nach dem anderen. Bei stale/fault den Moment auskosten: "Achtet auf die
Ampel — sie springt NICHT auf grün. Genau das ist der Sicherheitskern."
Danach Übergabe an Andi: "Das läuft nicht auf meinem Laptop — sondern auf echter Hardware."
-->

---

## [ Andi ] Betrieb — echt auf dem Raspberry Pi

Was ihr live seht, läuft in der **Zielumgebung**, nicht im Labor:

- 🖥️ **Raspberry Pi** — dieselbe Klasse Hardware wie im Feldbetrieb
- 🗄️ **native MariaDB 11.8** (kein Docker, E-35) — genau die DB, die die GL wollte (E-29)
- ⚙️ **uvicorn + systemd** — startet automatisch, läuft als Dienst

> dev = prod: keine Überraschungen zwischen Entwicklung und Betrieb.

<sub>④ technische Umsetzung · ⑤ Teamorganisation</sub>

<!--
ANDI spricht (~2 min). Dein Thema: Pi-Setup, MariaDB, Deployment. Schließ den Bogen zu E-29/E-35:
"Die Geschäftsleitung wollte MySQL wegen Wartbarkeit — hier ist es, nativ auf dem Pi, ohne
Container-Overhead." Zurück an Lucas: "Lucas, dein Fazit."
-->

---

<!-- _class: lead -->
# 6 · Team & Methode
### Wie wir organisiert waren

---

## Team & Methode — Wasserfall mit Disziplin

- **Vorgehen:** Wasserfall (bewusster Methodenvergleich mit G3/Scrum)
- **Klare Rollen/DRI:** Systemarchitektur, Backend-Devs, Test, Doku
- **Contract-first:** die API-Naht früh eingefroren → G1 & G3 arbeiten **parallel**, keine Wartezeiten
- **Kritischer Pfad geschützt:** Naht + Bewertungslogik auf die verlässlichsten Köpfe; abgegrenzte Tasks an den Rest
- **Prozess-Disziplin:** Feature-Branch → PR → Review → `main` (bleibt immer lauffähig)

<sub>⑤ Teamorganisation</sub>

<!--
LUCAS (~4 min, bei Zeitdruck auf 2 min kürzen). Contract-first als organisatorische Waffe, nicht
nur technisch. Ein Fehlmerge (#89) führte zu einer verschärften Merge-Regel — daraus wurde eine
dauerhafte Governance. Ehrlich, aber selbstbewusst: wir haben aus Fehlern Prozesse gemacht.
-->

---

<!-- _class: lead -->
# 7 · Ehrliche Reflexion
### Was lief gut, was war schwer, was bleibt offen

---

## Reflexion

**✅ Was lief gut**
Contract-first entblockte den kritischen Pfad · Fail-safe empirisch bestätigt (Fault/Stale/Ausfall → sauber `unknown`) · adversariale Reviews schlossen echte Sicherheitslücken

**⚠️ Was war schwer**
Zielkonflikt K1 (Fehlalarm ↔ Auslassung) — *nicht auflösbar, nur austarierbar* · eigene Push-Empfehlung durch Realität widerlegt

**❓ Was bleibt offen**
Messtechnische Kalibrierung · „defekt vs. still" bewusst vertagt (E-43) · Betriebsmodell lokal vs. Cloud (AE-01/02)

<sub>⑥ Reflexion</sub>

<!--
LUCAS (~2 min). Ehrlichkeit ist hier die Note. Nicht behaupten, alles sei perfekt. Der stärkste
Moment: "Die Demo ließ sich zeitweise nicht wiederholen — erste Vermutung: der Code ist kaputt.
Befund: der Code war intakt, der Fail-safe hat einen unrealistischen Simulator-Input korrekt
abgelehnt. Das System hat exakt das getan, was es sollte." Das ist Reflexionsreife auf Bestnote.
-->

---

## Ausblick & Kernbotschaft

**Bei mehr Zeit:** echter Eisindikator statt Proxy · messtechnische Kalibrierung am Realdatensatz ·
Cloud + Fernzugriff für Multi-Standort

---

> ## Aus einem widersprüchlichen Briefing wurde ein **fail-safe** Entscheidungssystem —
> ## das genau die zwei Fehler nicht mehr macht, an denen ANR gescheitert ist.

**Danke. Fragen?**

<!--
LUCAS (~30 s). Ruhig landen. Die Kernbotschaft ist der Rückbezug auf die zwei Vorfälle vom Anfang —
der Kreis schließt sich. Dann selbstbewusst in die Fragerunde. Backup-Folien für Detailfragen bereit.
-->

---

<!-- _class: lead -->
# Backup
### Detailfolien für die Fragerunde

---

## B1 · Live-Demo-Fallback

*(Hier Screenshot(s) des self-checking Showcase einsetzen: `ALLE N Schritte PASS`, Exitcode 0.)*

`![Showcase PASS](assets/showcase-pass.png)`

12 Schritte: health → green → thresholds(auth) → yellow → orange+WARNING → red+CRITICAL →
ack/double-ack(409) → stale → fault → recovery → audit → readings.

<!--
Falls die Live-Demo technisch scheitert: hierher springen. Der Screenshot beweist, dass der volle
Durchlauf grün ist. "Nie live ohne Netz."
-->

---

## B2 · Bewertungs-Details

- **Magnus-Formel** (Taupunkt): Konstanten `a = 17,62` · `b = 243,12 °C`
- **ΔT-Referenz unter 0 °C:** Reifpunkt `max(T_d, T_f)` statt Taupunkt (E-45) — hebt Risiko nur an
- **Feuchte-Definition:** „Oberfläche feucht" := `ΔT ≤ 1,0 °C` (nicht Luft-RH — E-33 entfernt)
- **Sicherheitsziele:** verpasste Vereisung FN = 0 % · Fehlalarm FP < 1 %

<!--
Für Nachfragen zur Bewertungslogik. E-33: der frühere RH≥90%-Term hätte Vorfall 1 als Fehlalarm
reproduziert — im Review entfernt.
-->

---

## B3 · Enums & Zielkonflikt K1

**Enums (Wire-Contract):** `RiskLevel` green/yellow/orange/red/**unknown** · `SensorStatus` ok/fault ·
`AlarmState` active/acknowledged/cleared · `AlarmSeverity` warning/critical

**K1 — der Dauerkonflikt:** Fehlalarm ↔ Auslassung. `flatline_timeout_min` ist ein Dual-Use-Parameter:
zugleich Fehlalarm-Schwelle **und** die maximale Zeit, die ein klemmender Sensor unentdeckt falsches
GRÜN liefern dürfte. Wir wählen konsistent fail-safe — mit dokumentiertem Preis.

<!--
Für Nachfragen zu Enums oder zum Kernkonflikt. K1 ist der intellektuell interessanteste Punkt —
wenn ein Dozent tief bohrt, hier landen.
-->

---

## B4 · Architektur — Mermaid-Quelle (für PNG-Export)

Für ein hochwertiges Diagramm: `Architekturdiagramm.md` (Systemkontext-Mermaid) nach
`assets/architektur.png` exportieren und auf Folie 13 einbetten.

Render-Optionen: GitHub (rendert Mermaid nativ, Screenshot) · mermaid.live · `mmdc -i … -o …`.

<!--
Nur ein Arbeitshinweis für die Folienpolitur, nicht projizieren. Der ASCII-Flow auf Folie 13
funktioniert auch ohne PNG.
-->
