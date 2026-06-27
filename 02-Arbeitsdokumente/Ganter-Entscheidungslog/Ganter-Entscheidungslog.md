# Persönliches Entscheidungslog — Luca Ganter (G2)

> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-27 · **Zeitraum:** 2026-06-23 bis 2026-06-27
> **Autor:** Luca Ganter · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

## 2026-06-23 — Konsumierten G1-Vertrag in eigene OpenAPI-Datei trennen
- **Kontext/Task:** DTB-19 (P1.2, OpenAPI v1) · FA-09/FA-01/FA-03 · Naht G1 → G2 → G3. Die DoD verlangt,
  auch den von G2 konsumierten G1-Vertrag (`GET /current`, `GET /health`) zu dokumentieren.
- **Entscheidung:** Den G1-Vertrag in eine **separate** Datei `g1-consumed.openapi.yaml` legen, getrennt von
  der eigenen G2-API-Spec `openapi.yaml` (beide unter `04-Source-code/docs/api/v1/`).
- **Begründung:** G2 hat in der Naht **zwei völlig verschiedene Rollen**: Gegenüber G3 sind wir der
  **Anbieter (Server)**, gegenüber G1 nur der **Abrufer (Client)**. Eine OpenAPI-Datei beschreibt aber
  immer genau **eine** API mit **einem** Server. Hätte ich G1s `/current` mit in unsere `openapi.yaml`
  gepackt, würde die Spec G1s Endpoint fälschlich als unseren eigenen ausweisen — mit falschem Server und
  ohne unser `/v1`-Präfix. Das hätte G3 (und uns selbst beim Implementieren) in die Irre geführt. Mit zwei
  Dateien bleibt jede für sich gültig und die Rollen sind eindeutig: `openapi.yaml` = was wir **anbieten**,
  `g1-consumed.openapi.yaml` = was wir **konsumieren**. Zusätzlich ist der Vertrag so leichter prüfbar (jede
  Datei einzeln validierbar) und beim späteren Einfrieren bleibt eindeutig, wer welchen Endpoint besitzt.
- **Alternativen:**
  - **G1 in dieselbe `openapi.yaml` mischen** — verworfen: erzeugt Rollen-Verwechslung und semantisch
    falsche Server-/Pfad-Angaben.
  - **G1 nur in Prosa/Markdown dokumentieren** (statt OpenAPI) — verworfen: weniger maschinenlesbar/prüfbar;
    eine echte Spec lässt sich validieren und von G2s Poller als Referenz nutzen.
  - **G1 gar nicht dokumentieren** — verworfen: verstößt gegen die Architekten-Vorlage (DTB-19, Punkt 6).
- **Ergebnis/Status:** umgesetzt. Beide Dateien mit `openapi-spec-validator` geprüft; das santa-loop-Review
  bestätigte die Rollen-Trennung G1/G2 ausdrücklich als sauber.

## 2026-06-23 — Double-Ack: `409 Conflict` statt idempotent
- **Kontext/Task:** DTB-19 (P1.2) · PR #48 Review-Finding [MEDIUM] · NF-09 (Audit/Nachvollziehbarkeit) · RB-01.
  Offen war: Was passiert bei `POST /v1/alarms/{id}/ack`, wenn der Alarm schon quittiert ist?
- **Entscheidung:** Erneute Quittierung eines bereits `acknowledged`/`cleared` Alarms wird mit **`409
  Conflict`** abgelehnt — die Operation ist **nicht idempotent**. (Alternative wäre gewesen, ein zweites Ack
  still als `200` durchzulassen.)
- **Begründung:** NF-09 verlangt ein nachvollziehbares Audit-Log. Würde ein zweites Ack lautlos als `200`
  akzeptiert, gäbe es keinen klaren Hinweis auf das versehentliche Doppel-Quittieren, und es bliebe unscharf,
  welche Quittierung „zählt". Mit `409` lehnt das System die Doppel-Quittierung **explizit** ab: der
  Alarm-Zustand bleibt eindeutig und jede gültige Quittierung ist genau **ein** Audit-Eintrag. Das `409`
  signalisiert dem Frontend zudem klar „Zustand bereits geändert" — sauberer als stilles Schlucken, gerade
  weil bei RB-01 der Mensch die eigentliche Entscheidung trägt.
- **Alternativen:**
  - **Idempotent (zweites Ack → `200`, no-op)** — verworfen: schluckt versehentliche Doppel-Acks lautlos,
    schwächt die Audit-Klarheit (NF-09).
  - **Jedes Ack erneut loggen (mehrfaches Quittieren erlaubt)** — verworfen: bläht das Audit-Log mit
    redundanten Einträgen auf; relevant ist die eine Erst-Quittierung.
- **Ergebnis/Status:** umgesetzt in `openapi.yaml` (`409`-Response + Description, Auslösebedingung
  `acknowledged`/`cleared`), validiert, Teil von PR #48. Reaktion auf das Reviewer-Finding (Reviewer hatte
  `409` oder dokumentierte Idempotenz als Optionen genannt).

## 2026-06-24 — Taupunkt-Funktion als strikter Rechner: `ValueError` statt stillem Ersatzwert (DTB-32)
- **Kontext/Task:** DTB-32 (P2.3, Taupunkt nach Magnus) · NF-01 (Fail-safe) · Naht zu DTB-60 (Poller) und
  DTB-38 (Bewertung). Ich hatte `calculate_dew_point(air_temp_c, humidity_pct)` zuerst geradlinig
  implementiert (Magnus, a=17,62 / b=243,12 aus `Schwellenwerte.md §1`). Ein santa-loop-Review deckte zwei
  Fail-safe-Brüche an den Rändern auf: (1) bei `humidity_pct = 0` warf meine Funktion einen `ValueError`,
  während der Poller (`poller.py`) RH=0 durchlässt — eine **Naht-Kollision**, die im Bewertungspfad zu einem
  ungefangenen Absturz führen kann; (2) bei `air_temp_c = NaN` lieferte die Funktion ein **stilles `nan`**,
  das die spätere Bewertungskaskade über die ΔT-Vergleiche fälschlich auf **GRÜN** durchfallen lässt.
- **Entscheidung:** Die Funktion bleibt ein **strikter Rechner**. Bei nicht bestimmbarer oder ungültiger
  Eingabe (RH ∉ (0, 100], nicht-endliche Temperatur NaN/inf, Magnus-Pol bei T_a = −b) wirft sie einen
  **`ValueError`** und liefert bewusst **kein** stilles Ersatzergebnis. Die eigentliche Fail-safe-Reaktion
  (fehlender Taupunkt → konservativ ≥ GELB) baue ich **nicht** in diese Funktion ein, sondern lege sie als
  **dokumentierte Auflage** auf den Aufrufer: DTB-60 (Poller) muss den `ValueError` fangen und
  `dew_point_c = None` speichern; DTB-38 (Bewertung) stuft den fehlenden T_d konservativ ein.
- **Begründung:** Ich trenne bewusst **Berechnung** und **Sicherheits-Policy**. Die Aufgabe dieser reinen
  Funktion ist, einen Taupunkt zu rechnen **oder klar zu signalisieren, dass das nicht geht** — nicht, zu
  entscheiden, welche Ampelstufe daraus folgt. Diese Stufen-Entscheidung gehört in die Bewertungslogik
  (DTB-38), den hoch getesteten Kern. Eine geworfene Exception ist ein **explizites, fangbares Signal**;
  genau das ist der Gegenentwurf zum stillen `nan`, das wie eine gültige Zahl aussieht, sich weiterpflanzt
  und die Kaskade unbemerkt auf GRÜN kippt — der konkrete NF-01-Verstoß. Indem Berechnung und Policy in
  getrennten Modulen liegen, bleibt jedes für sich testbar, und die Naht-Inkonsistenz löse ich über einen
  **klaren Vertrag** (Aufrufer fängt und behandelt), nicht durch stilles Aufweichen einer Seite.
- **Alternativen:**
  - **`None`-Sentinel zurückgeben** (Signatur `float | None`): verworfen — verlagert die Policy zwar auch zum
    Aufrufer, aber `None` lässt sich leichter übersehen als eine Exception (ein vergessenes `if td is None`
    führt erneut zu stillem Fehlverhalten) und vermischt „kein Ergebnis" mit dem normalen Rückgabetyp. Eine
    Exception **erzwingt** eine bewusste Behandlung.
  - **Schema/Poller sofort mit anpassen** (`humidity_pct: Field(gt=0)`): verworfen für jetzt — würde den
    Scope von DTB-32 in DTB-12 (Datenmodell) und DTB-60 (Poller) ausweiten und mehrere Tickets/Tests
    berühren, bevor die Naht mit dem Architekten final abgestimmt ist. Kann später als eigene, bewusste
    Entscheidung folgen.
  - **Fail-safe-Default direkt in der Funktion** (z. B. bei RH=0 einfach T_a zurückgeben): verworfen — das
    wäre genau das stille, plausibel aussehende Ersatzergebnis, das NF-01 verbietet; die Funktion würde eine
    Sicherheitsentscheidung treffen, die ihr nicht zusteht.
- **Ergebnis/Status:** umgesetzt. `calculate_dew_point` mit Guards (RH-Bereich, `math.isfinite`,
  Magnus-Pol); 20 Unit-Tests grün, inkl. Frost-/Negativ-Referenzwerten (−2,1/92 → −3,225 °C;
  −10/80 → −12,797 °C) und Guard-Tests; Coverage `assessment` = 100 %. Branch
  `feat/dtb-32-taupunkt-magnus` gepusht (PR/Merge offen, Lucas-Freigabe). **Offene Folge-Auflage:** Bei der
  Umsetzung von DTB-60 den `ValueError` fangen → `dew_point_c = None` → DTB-38 fail-safe ≥ GELB; dort
  verifizieren.

## 2026-06-25 — Unplausiblen Taupunkt verwerfen statt speichern (DTB-60)
- **Kontext/Task:** DTB-60 (Taupunkt im Poller) · NF-01 (Fail-safe) · `Schwellenwerte.md` §3 (Sensor-Defekt).
  DTB-60 setzt die Folge-Auflage aus DTB-32 um: der Poller ruft `calculate_dew_point(air_temp_c,
  humidity_pct)` und füllt `Reading.dew_point_c`, fängt den `ValueError` (RH=0) → `dew_point_c=None`. Ein
  santa-loop-Review fand danach einen **weiteren stillen Fail-safe-Bruch (H1):** Der Poller lässt
  `humidity_pct` in `[0, 100]` zu, `calculate_dew_point` wirft aber nur bei *exakt* RH=0. Im Spalt knapp
  über 0 (z. B. 0,01 %, ein defekter Sensorwert) liefert die Formel einen absurden Taupunkt
  (−83 / −143 °C), der klaglos gespeichert würde → downstream riesiges ΔT → „keine Feuchte" → fälschlich GRÜN.
- **Entscheidung:** Den **berechneten Taupunkt plausibilisieren**: liegt `dew_point_c` unter der ohnehin
  gültigen Sensor-Temperaturgrenze `MIN_TEMP_C` (−50 °C), wird er als unplausibel verworfen →
  `dew_point_c=None` (derselbe Fail-safe-Pfad wie bei RH=0). Das Reading wird mit den übrigen gültigen
  Werten trotzdem gespeichert.
- **Begründung:** Ein Taupunkt unter −50 °C ist bei einem Sensor, der selbst nur bis −50 °C plausibel misst,
  physikalisch nicht haltbar und ein klares Indiz für einen defekten Eingangswert (`Schwellenwerte.md` §3).
  Ich prüfe bewusst das **Ergebnis** statt eine neue Feuchte-Untergrenze einzuführen: das nutzt eine
  **bereits existierende, begründete Konstante** (`MIN_TEMP_C`) wieder, erfindet keinen zusätzlichen
  Domänen-Schwellenwert, der separat abgestimmt/parametriert werden müsste, und schließt den ganzen
  „RH-fast-0"-Spalt in einem Schritt. Frost-Taupunkte (z. B. −12,8 °C) bleiben unangetastet — der
  Use-Case-Kern (Vereisung unter 0 °C) wird nicht beschnitten. Konsistent mit der DTB-32-Linie: lieber
  `None` (klares „unbestimmbar") als ein plausibel aussehender, aber falscher Wert.
- **Alternativen:**
  - **Untere Feuchte-Plausibilitätsgrenze im Poller** (z. B. RH < 1 % = defekt): verworfen — schließt zwar
    die Quelle direkt, führt aber einen neuen, frei gewählten Domänen-Schwellenwert ein, der gegen Realdaten
    begründet und (NF-05) parametriert werden müsste — mehr Begründungslast für denselben Schutz.
  - **H1 als Folge-Ticket vertagen** (Validierung in DTB-12): verworfen — der stille-GRÜN-Pfad bliebe bis
    dahin offen; bei einem Sicherheitssystem nicht akzeptabel, wenn ein kleiner, lokaler Fix genügt.
- **Ergebnis/Status:** umgesetzt. Poller berechnet **und** plausibilisiert `dew_point_c`; 4 neue
  Poller-Tests (Berechnung 1,2/96 → 0,63 °C; Frost −5/80 → −7,92 °C; RH=0 → None; RH=0,01 → None), volle
  Suite 86 grün, Coverage `poller.py` = 100 %. Branch `feat/dtb-60-poller-taupunkt` (gestapelt auf DTB-32)
  gepusht; PR/Merge offen (Lucas-Freigabe, nach DTB-32). **Offene Folge-Auflage (an DTB-38/DTB-12):** Die
  Bewertung muss `dew_point_c=None` explizit als „Feuchte vorhanden = wahr" behandeln (`Schwellenwerte.md`
  §2 → nie GRÜN); als eigenes Ticket zu verlinken.

## 2026-06-25 — Stale-Erkennung im Poller: verwerfen + testbare Uhr + Clock-Skew-Guard (DTB-58)
- **Kontext/Task:** DTB-58 (Stale-Erkennung G1-Snapshots) · FA-04 (veraltete Daten nicht als aktuell zeigen) ·
  NF-01 (Fail-safe: Stale/Ausfall nie GRÜN) · `Schwellenwerte.md §3` (Stale-Timeout 120 s, parametrierbar).
  Aufgabe: Der Poller erkennt Snapshots, deren `measured_at` älter als 120 s ist. Ein `santa-loop`-Review
  (zwei adversariale Prüfer) deckte danach zwei zusätzliche Punkte auf.
- **Entscheidung:** (1) Stale Snapshots (Alter > 120 s) werden **fail-safe verworfen** (geloggt, `None`) —
  **nicht** als „stale" markiert und gespeichert. (2) Die aktuelle Zeit kapsele ich in einen Helper `_now()`,
  damit Tests die Uhr deterministisch einfrieren können. (3) Ein **Clock-Skew-/Zukunfts-Guard** ergänzt die
  einseitige Altersprüfung: liegt `measured_at` mehr als `MAX_CLOCK_SKEW_S` (5 s) in der Zukunft, wird der
  Snapshot ebenfalls verworfen. (4) Die Schwelle bleibt benannte Konstante `STALE_MAX_AGE_S`; die
  Config-Anbindung (NF-05) verschiebe ich bewusst auf DTB-43.
- **Begründung:**
  - *Verwerfen statt markieren:* Die Prüfer forderten, das Reading als „unknown" zu markieren statt zu verwerfen.
    Ich habe geprüft, was das real bedeutet: `Reading` (DTB-12) hat **kein** `is_stale`-Feld (`extra="forbid"`),
    `SensorStatus` kennt kein `STALE`, und `assess_ice_risk` (DTB-38) kennt keine Staleness. Echtes Markieren
    würde also das **eingefrorene Datenmodell (DTB-12, Architekten-Naht)** und den **fremden kritischen Pfad
    (DTB-38)** ändern — weit über DTB-58 hinaus. Das ist eine Naht-Entscheidung des Architekten, die ich nicht
    eigenmächtig treffe. Zugleich steckt die Staleness ohnehin schon in `measured_at`, und **DTB-43 ist genau
    dafür speziert** (Alter an der Lese-Grenze → `risk_level=unknown`) — die Fail-safe-Kette schließt dort,
    egal ob ich verwerfe oder markiere. Also: ticket-konform verwerfen (sicher, in-scope) und die Frage
    sichtbar für den Architekten markieren (im Code an der Discard-Stelle + im PR).
  - *`_now()`-Seam:* Die bestehende Test-Fixture nutzt einen festen `measured_at` (2026-06-23). Gegen die echte
    Uhr wäre dieser Wert dauerhaft „stale" → alle bestehenden Tests bräche. Eine dynamische Fixture würde die
    Exakt-Wert-Asserts (`measured_at == datetime(2026,6,23,…)`) brechen. Der `_now()`-Seam erlaubt eine
    autouse-Fixture, die die Uhr nahe dem Fixture-Zeitstempel **einfriert** → bestehende Asserts bleiben gültig
    **und** die Zeit ist deterministisch.
  - *Clock-Skew-Guard:* Die naive Prüfung `age > 120` ist einseitig — ein `measured_at` in der Zukunft (defekte/
    vorlaufende G1-Uhr) ergibt **negatives** age → nie stale → würde als „frisch" gespeichert (ein Fail-safe-Loch,
    NF-01). Darum lehne ich weit voraus liegende Zeiten ab. Eine **kleine** Toleranz (`MAX_CLOCK_SKEW_S`) bleibt,
    weil ein Sub-Sekunden-Vorlauf (NTP-Drift) normal ist und ein Komplett-Ablehnen sonst zum Dauer-`unknown`
    (faktisch DoS) führte. Der 5-s-Wert ist ein **KI-Vorschlag** und gegen den Realbetrieb zu plausibilisieren.
- **Alternativen:**
  - **Stale als `unknown` markieren (is_stale-Feld + DTB-38):** verworfen für diesen PR — Änderung an der
    eingefrorenen Naht (DTB-12) + fremdem kritischen Pfad (DTB-38); gehört dem Architekten; DTB-43 schließt die
    Kette ohnehin. Als offene Frage weitergegeben statt eigenmächtig entschieden.
  - **Dynamische frische Fixture (`measured_at = now`):** verworfen — bricht die Exakt-Wert-Asserts; der
    `_now()`-Seam ist sauberer und sichert den tz-Vertrag separat ab (`test_now_is_timezone_aware`).
  - **Zukunfts-Timestamps ganz ohne Toleranz ablehnen:** verworfen — bei vorlaufender G1-Uhr würde gar nichts
    mehr gespeichert (Dauer-`unknown`/DoS).
  - **Schwelle hartcodieren ohne Flag:** verworfen — verfehlte stillschweigend die NF-05-Parametrierbarkeit
    (DTB-43); benannte Konstante + ausdrücklicher Verweis ist ehrlicher.
- **Ergebnis/Status:** umgesetzt + per `santa-loop`, `code-/python-/security-review`, `verification-loop`
  geprüft; gefundenes Clock-Skew-CRITICAL gefixt. 160 passed / 9 skipped, `poller.py` Coverage **100 %**, ruff
  sauber. Commits `802b8b0`/`97c26e5`/`24f89bc` in **PR #66** (mit DTB-60 gebündelt, Lucas-Freigabe offen).
  **Offen:** Naht-Entscheidung (verwerfen vs. markieren) für Architekt; Config-Anbindung der Schwellen via DTB-43.

## 2026-06-25 — Magnus-Pol-Guard: Toleranzvergleich statt Float-Gleichheit (DTB-32)
- **Kontext/Task:** Review-Befund zu `calculate_dew_point` (DTB-32). Der Pol-Guard `if MAGNUS_B + air_temp_c == 0`
  fängt nur den **Exaktwert** −243,12; durch Einlesen/Umrechnung/Rundung entstandene Nachbarwerte
  (z. B. −243,120000000001) rutschen still durch und teilen durch nahezu null → physikalisch unsinniges
  Riesen-Ergebnis statt eines fangbaren Fehlers.
- **Entscheidung:** Den Guard auf einen **Toleranzvergleich** umstellen:
  `abs(MAGNUS_B + air_temp_c) < POLE_TOLERANCE_C` mit benannter Konstante `POLE_TOLERANCE_C = 1e-9`.
- **Begründung:** Float-Gleichheit auf 0 ist ein bekanntes Antipattern; eine **absolute** Toleranz fängt auch die
  gerundeten Pol-Nachbarwerte ab und macht den Guard fail-safe (NF-01: lieber ein fangbarer `ValueError` als ein
  scheinbar gültiges, falsches Ergebnis). **Absolute** Toleranz (statt relativer via `math.isclose`), weil der Pol
  ein fester, bekannter Wert (−b) ist und der relevante Abstand in denselben Einheiten (°C) gemessen wird — ein
  relativer Bezugswert wäre hier unklar/überdimensioniert. `1e-9` ist klein genug, dass nur praktisch-am-Pol-Werte
  getroffen werden, und ein **KI-Vorschlag**, der gegen die Quelle plausibel zu halten ist.
- **Alternativen:**
  - **`math.isclose(..., abs_tol=…)`:** verworfen — gleicher Effekt, aber mehr Mechanik und eine unnötige
    Bezugswert-/`rel_tol`-Frage.
  - **`== 0` belassen:** verworfen — genau der Bug (greift nur am Exaktwert).
- **Ergebnis/Status:** umgesetzt per TDD (parametrisierter Nahe-Pol-Test RED→GREEN); 22 Assessment-Tests grün,
  Coverage `assessment` 100 %, ruff sauber. **Direkt auf PR #79** (`feat/dtb-32-taupunkt-magnus`, `96bfb26`)
  ergänzt, nachdem die ältere Dublette #75 (geschlossen) den Fix nicht trug — #79 ist damit die vollständige,
  aktuelle DTB-32-Version.

## 2026-06-27 — Flatline-Erkennung als Fenster-/Spannweiten-Logik im Poller (DTB-20)
- **Kontext/Task:** DTB-20 (Sensor-Defekt-Erkennung Flatline/Sprung im G1-Poller verdrahten) · FA-04 ·
  NF-01 (Fail-safe) · `Schwellenwerte.md §3` (Sensor defekt: Bereich/Flatline/Sprung/Timeout). `check_plausibility`
  (Sprung + Zeitstempelordnung) existierte schon; meine Aufgabe war die **Flatline**-Erkennung zu ergänzen und
  beides im Poller (`src/ingest/poller.py`) gegen den G1-Snapshot-Strom zu verdrahten.
- **Entscheidung:** Flatline **nicht** als Vergleich „Reading vs. unmittelbarer Vorgänger", sondern als
  **Zeitfenster + Spannweite**. Neue reine Funktion `check_flatline(window_start, current_measured_at,
  temp_span_c, thresholds)`; den **Fenster-Zustand** (`window_start`, `temp_min`/`temp_max`) hält der Poller
  **pro Sensor**. `check_plausibility` habe ich um den Flatline-Teil entschlackt (jetzt nur noch Sprung +
  Zeitstempelordnung). `flatline_epsilon_c` von Dummy `0,01` auf **`0,15`** kalibriert.
- **Begründung:** Das Design ist über **drei `santa-loop`-Runden** gereift — jede Runde fand einen echten Defekt,
  den ich geschlossen habe:
  - *Runde 1 (CRITICAL):* Die naive „Vergleich mit unmittelbarem Vorgänger"-Logik ist bei **30-s-Polling tot** —
    der Abstand zwischen zwei aufeinanderfolgenden Polls erreicht nie die 15-min-Flatline-Dauer, die Erkennung
    würde **nie feuern**. Lösung: ein **Fenster**. `window_start` = ältestes Reading, seit dem die Temperatur das
    Band nicht verlassen hat; Flatline feuert, wenn `jetzt − window_start ≥ 15 min` **und** die Spannweite ≤ ε
    bleibt. So werden ~30 Readings über 15 min ausgewertet, nicht zwei 15 min auseinanderliegende Punkte.
  - *Runde 2 (CRITICAL):* Punkt-Anker + ε=0,01 → **Dither-Escape**: ein klemmender, leicht zappelnder Sensor
    (±1 LSB) entkommt, weil der Abstand zu **einem** Ankerpunkt das schmale Band ständig überschreitet und das
    Fenster zurücksetzt. Lösung: **Spannweite (max − min) über das Fenster** statt Abstand zu einem Punkt, **plus
    ε an die Sensorauflösung kalibriert**. Der DS18B20 ist 12-bit (LSB 0,0625 °C); ±1-LSB-Rauschen ⇒ ε ≈ 2×LSB
    ≈ **0,15** (vom Architekten autorisiert).
  - *Schicht-Trennung:* `check_flatline` bleibt **rein/zustandslos** (in Isolation testbar), der Fenster-Zustand
    gehört in den Poller, weil nur er den Messstrom **pro Sensor** hält — konsistent zu `_now()`/`_last_reading`.
- **Alternativen:**
  - **Reading-vs-Vorgänger (`delta_min`):** verworfen — Runde-1-CRITICAL, bei 30-s-Polling funktionslos.
  - **Punkt-Anker + festes ε=0,01:** verworfen — Runde-2-CRITICAL, Dither-Escape eines zappelnden Stuck-Sensors.
  - **Fenster-Zustand IN die reine Funktion legen:** verworfen — würde sie zustandsbehaftet und schwer testbar
    machen und die Schichtgrenze (Berechnung vs. Stream-Haltung) durchbrechen.
  - **ε frei wählen:** verworfen — Schwellen kommen aus der Quelle, nicht aus der Luft; ε ist an die
    DS18B20-Auflösung gekoppelt und mit dem Architekten plausibilisiert. **Offen:** Bit-Auflösung mit G1 final
    bestätigen (rein Config, falls abweichend).
- **Ergebnis/Status:** umgesetzt + 3× `santa-loop`-geprüft, **beide CRITICALs geschlossen**. Tests decken die
  Fenster-/Dither-/Recovery-Fälle ab, u. a. „30 flache Polls → flatline", „±1-LSB-Dither über 40 Polls →
  flatline" und „Erholung, sobald die Temperatur sich real bewegt". **533 passed / 16 skipped**, Coverage
  `poller.py` 99 % / `failsafe.py` 98 %, ruff sauber. Commit `3b78d56` auf `feat/dtb-20-defekt-erkennung`, auf
  `origin/main` gemergt (`a9a7f4e`) und gepusht. PR/Merge offen (Lucas-Freigabe).

## 2026-06-27 — `flatline_timeout_min` bei 15 belassen statt lockern (DTB-20, Option 1)
- **Kontext/Task:** Aus der Fenster-Logik (Eintrag oben) folgt eine **Designspannung**, die ein `santa-loop`-Prüfer
  in Runde 3 sauber benannte (**kein Bug**, Suite grün): ε=0,15 erzeugt eine Fehlalarm-Schwelle
  `ε / Timeout = 0,15 / 15 min = 0,6 °C/h` — eine **gesunde**, real *langsam* driftende Oberflächentemperatur
  (< 0,6 °C/h) bewegt sich über 15 min weniger als ε und wird als „eingefroren → `unknown`" verworfen.
  Stuck-Sensor und Schleich-Drift sehen über das Fenster gleich aus. Der Architekt (Lucas) bestätigte den
  Trade-off und stellte zwei Wege zur Wahl: **(1)** 15 lassen + akzeptieren, **(2)** Timeout 15 → 30 (Schwelle
  dann 0,3 °C/h). NF-01 · K1 (Fehlalarm ↔ Auslassung) · `Schwellenwerte.md §3`.
- **Entscheidung:** **Option 1** — `flatline_timeout_min` bei **15** belassen, den Fehlalarm bei gesunder
  Schleich-Drift **bewusst akzeptieren** (er ist fail-safe-Richtung: nie GRÜN, nur `unknown`), den Trade-off
  dokumentieren und ein **Tuning-Ticket** anlegen. Die eigentliche Wurzel (ε=0,15 vs. tatsächliche
  Sensorauflösung) wird später mit den **G1-Finalwerten** kalibriert — **nicht** jetzt über die Fensterbreite
  verbogen.
- **Begründung:** `flatline_timeout_min` ist nicht nur die Fehlalarm-Schwelle, sondern auch die **Zeit, die ein
  klemmender Sensor unentdeckt falsche Werte liefern darf**. Ein bei z. B. +2 °C eingefrorener Sensor schiebt
  mit **frischen Zeitstempeln** (der Stale-Timeout greift nicht, weil `measured_at` weiterläuft) ein **falsches
  GRÜN**, bis die Flatline-Erkennung nach `timeout` greift. Option 2 (30) **verdoppelt** dieses Zeitfenster — sie
  verringert die *harmlose* Fehlersorte (false-`unknown`, fail-safe) und erkauft das mit der **doppelten Zeit in
  der gefährlichen Richtung (falsches GRÜN)**. Das läuft gegen die Projekt-Maxime „lieber zehn Fehlalarme als ein
  vereistes Flugzeug" (NF-01): sichere Fehler sind vorzuziehen ⇒ **kürzere** Flatline-Zeit ist das sichere
  Verhalten. Zudem deckt sich **15** exakt mit `Schwellenwerte.md §3` („keine Änderung > 15 min") → **null
  Doc-Drift**; Option 2 wäre eine Abweichung von der Schwellen-Quelle und müsste die Doc mitziehen. Die offene
  empirische Frage — wie häufig reale Drift < 0,6 °C/h nahe 0 °C ist und ob das Alarm-Müdigkeit (K1) erzeugt —
  lässt sich **vom Schreibtisch nicht** beantworten; der sichere Default ist **enge Erkennung jetzt +
  Nachkalibrierung per Ticket mit echten Daten**.
- **Alternativen:**
  - **Option 2 (`flatline_timeout_min` = 30):** verworfen — verdoppelt die Zeit, in der ein Stuck-Sensor ein
    falsches GRÜN halten kann (gefährliche Fehlerrichtung), und weicht von `Schwellenwerte.md §3` ab. Nur
    verteidigbar, **wenn** häufige reale Schleich-Drift nahe 0 °C → Alarm-Müdigkeit belegt ist — das ist es nicht.
  - **ε wieder senken (statt am Timeout zu drehen):** verworfen — öffnet den Dither-Escape (Runde-2-CRITICAL)
    erneut.
  - **Trade-off ignorieren / DTB-20 einfach „done" melden:** verworfen — sicherheitsrelevant; muss bewusst
    entschieden **und** dokumentiert sein, bevor die Task abschließbar ist.
- **Ergebnis/Status:** **Option 1 entschieden**; **keine Code-Änderung nötig** (Config steht bereits auf 15,
  doc-konsistent). Ich habe mich dazu **bewusst mit dem Architekten (Lucas) beraten** und mich nach Abwägung der
  beiden Fehlerrichtungen **bewusst für 15 statt 30 Minuten entschieden** — gerade *weil* es eine
  **sicherheitsrelevante** Entscheidung ist: das kürzere Fenster erkennt einen klemmenden Sensor, der sonst mit
  frischen Zeitstempeln ein falsches GRÜN halten könnte, doppelt so schnell. Den damit in Kauf genommenen
  Fehlalarm bei gesunder Schleich-Drift (fail-safe-Richtung, nur `unknown`) trage ich bewusst mit. Trade-off hier
  dokumentiert; **Tuning-Ticket angelegt** (**DTB-69**, Lucas zugewiesen — ε und `flatline_timeout_min` gegen die
  finale G1-Sensorauflösung + reale Drift-Statistik nachkalibrieren; G1-Anfrage als Kommentar). Konsens mit dem
  Architekten (Lucas).
- **Offene Koordination (Stand 2026-06-27, ehrlich festgehalten):** Beim Sync auf `main` ist aufgefallen, dass
  DTB-20 **parallel** über **PR #120** (`fix/dtb-20-flatline-epsilon-ds18b20`, bereits gemergt) gelöst wurde —
  dort als reine **ε-Kalibrierung (0,15) + Dither-Regressionstest** auf der bestehenden DTB-13-Logik (Flatline
  bleibt **in** `check_plausibility`, Vergleich gegen *ein* Vorgänger-Reading). Mein Branch geht weiter: Ich
  ziehe die Flatline in eine **fenster-/spannweitenbasierte** `check_flatline` und verdrahte sie in den Poller —
  weil der Single-Point-Vergleich bei 30-s-Polling nicht zuverlässig die 15-min-Dauer erreicht und gegen Dither
  anfälliger ist. Dadurch bricht der von #120 gemergte Regressionstest `test_check_plausibility_lsb_dither_is_flatline`.
  **Bewusste Entscheidung:** ich pushe meinen Code-Branch **nicht** eigenmächtig und überschreibe die fremde,
  gemergte Arbeit nicht, sondern kläre zuerst mit Lucas + dem #120-Autor, welches Design gewinnt (mein Fenster
  vs. mains Single-Point). Dieser Log-Eintrag dokumentiert meine Variante + Begründung als Diskussionsgrundlage.
