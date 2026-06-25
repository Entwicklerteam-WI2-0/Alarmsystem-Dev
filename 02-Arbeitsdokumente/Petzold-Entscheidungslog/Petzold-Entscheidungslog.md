# Persönliches Entscheidungslog — Johannes Petzold (G2)
> **Erstellt am:** 2026-06-22 · **Letzte Bearbeitung:** 2026-06-23  ·  **Zeitraum:** 2026-06-22 bis 2026-06-23
> **Autor:** Johannes Petzold · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

> ℹ️ Die Felder **Begründung** sind bewusst offen (`[➜ von dir]`) — sie gehören deiner Einzelleistung und
> müssen von dir formuliert werden. Kontext, Entscheidung, Alternativen und Status sind als Faktengerüst
> vorbereitet; bitte prüfen und bei Bedarf korrigieren.

---

## 2026-06-22 — Trigger des CI-Workflows auf `main` beschränkt (Abweichung vom DoD-Wortlaut)
- **Kontext/Task:** DTB-11 (CI/CD-Setup `.github/workflows/test.yml`) · M2 · DoD-Punkt „Trigger: `on: [push, pull_request]`"
- **Entscheidung:** `on: push: branches: [main]` + `pull_request:` — statt des wörtlichen `on: [push, pull_request]`.
- **Begründung:** Doppelläufe verschwenden Actions-Minuten und können Verwirrung bei den Statusanzeigen hervorrufen (zwei parallele Check-Läufe pro PR). Eine Abweichung vom DoD-Wortlaut zur Prozessbeschleunigung ist vertretbar, solange die Grundlagen und weiteren Vorgaben erhalten bleiben — die eigentliche DoD-Absicht (CI prüft vor dem Merge) bleibt über den `pull_request`-Trigger gewahrt. Die Abweichung wird nicht eigenmächtig festgelegt, sondern gemeinsam mit Lucas als Systemarchitekt abgesprochen und entschieden, um Konflikte zu vermeiden und verschiedene Blickwinkel zu beleuchten.
- **Alternativen (erwogen/verworfen):**
  - *Wörtlich `[push, pull_request]`:* CI läuft bei jedem Push auf jedem Branch → bei offenem PR **doppelte Läufe** (einmal `push`, einmal `pull_request`). Verworfen wegen Redundanz (Review-Finding LOW).
  - *Nur `pull_request`:* kein CI bei direktem Push auf `main`. Verworfen — `main` soll auch bei direktem Stand geprüft werden.
- **Ergebnis/Status:** umgesetzt in PR #18. **Abweichung vom DoD-Wortlaut** bewusst dokumentiert; der Status-Check für „Require status checks" funktioniert über den `pull_request`-Trigger. Finale Festlegung (DoD-Wortlaut vs. Review-Variante) noch **offen** → mit Lucas/Team abstimmen.

## 2026-06-22 — Laufzeit- und Entwicklungsabhängigkeiten getrennt
- **Kontext/Task:** DTB-11 · Review-Finding (MEDIUM)
- **Entscheidung:** `requirements.txt` (nur Laufzeit: FastAPI, Uvicorn, Pydantic) + `requirements-dev.txt` (Test/CI: pytest, pytest-cov, httpx); der Workflow installiert beide explizit.
- **Begründung:** Es ist von Beginn an sauberer, Laufzeit- und Dev-Abhängigkeiten zu trennen, um späteren Problemen vorzubeugen. Wird es zu Projektbeginn ordentlich gemacht, spart das über das gesamte Projekt Zeit und Aufwand. Damit ist es jetzt nur ein kleiner Mehraufwand, während eine spätere Trennung mit großen Testaufwänden verbunden sein könnte, die die Weiterarbeit verhindern oder verschlechtern würden. Auch ohne aktuellen Produktions-Deploy ist die Trennung damit eine günstige Vorsorge, kein Selbstzweck.
- **Alternativen (erwogen/verworfen):**
  - *Eine gemeinsame `requirements.txt`:* würde in einer Laufzeit-/Produktionsumgebung die Test-Tools mitinstallieren. Verworfen (sauberere Trennung, auch wenn aktuell kein Prod-Deploy existiert).
  - *Optional-Dependencies in `pyproject.toml` (extras):* idiomatisch, aber es gibt noch kein `pyproject.toml` und mehr Setup-Aufwand. Zurückgestellt (kommt ggf. mit DTB-25).
- **Ergebnis/Status:** umgesetzt in PR #18.

## 2026-06-22 — Direktabhängigkeiten mit `~=` gepinnt
- **Kontext/Task:** DTB-11 · Review-Finding (MEDIUM)
- **Entscheidung:** alle Direktabhängigkeiten mit `~=` (compatible release) versionieren, z. B. `fastapi~=0.115`.
- **Begründung:** Mit dieser Variante lassen sich nur kompatible Updates zu, die die Funktionsfähigkeit nicht beeinträchtigen. So wird verhindert, dass eine fehlerhafte Update-Version das System zum Zusammenbruch bringt — man kann abwarten und gezielt auf eine funktionierende Version aktualisieren. Gleichzeitig bleibt man flexibler und kann mit verschiedenen Versionen arbeiten und testen, statt sich auf eine starre Version (`==`) festzulegen. Ein vollständiges Lockfile (auch transitive Deps) wäre maximal reproduzierbar, bringt aber zusätzlichen Tooling-Aufwand und wurde für die aktuelle Prototyp-Phase bewusst zurückgestellt.
- **Alternativen (erwogen/verworfen):**
  - *Ungepinnt:* ein Breaking-Release (z. B. Pydantic v1→v2) bricht den Build lautlos. Verworfen.
  - *Exakt `==`:* maximale Reproduzierbarkeit, aber starr und höherer Update-Aufwand. Verworfen für ein bewegliches Prototyp-Projekt.
  - *Lockfile (`pip-compile`/`requirements.lock`):* friert auch transitive Deps ein, braucht aber zusätzliches Tooling. **Bewusst auf M2/M3 verschoben** (Reviewer-Konsens: für den Prototyp jetzt vertretbar).
- **Ergebnis/Status:** umgesetzt in PR #18; Lockfile als spätere Option notiert.

## 2026-06-22 — Korrekturen über neuen Branch statt Ruleset-Änderung
- **Kontext/Task:** DTB-11 · GitHub-Ruleset blockt Pushes auf bestehende Feature-Branches („Changes must be made through a pull request")
- **Entscheidung:** Review-Korrekturen über einen **neuen Branch + neuen PR** einspielen (PR #18), statt das Ruleset selbst anzupassen — obwohl Adminrechte vorhanden wären.
- **Begründung:** Lucas hat die Hauptkonvention, die nicht gebrochen wird. Meine Adminrechte sind nur dafür da, bestimmte Settings bearbeiten und ausführen zu können — nicht, um andere Arbeitskonventionen zu überschreiben. Auch wenn ich die Rolle Systemarchitekt mit Lucas teile, liegt die Pflege-Hoheit über die Branch-Protection bei ihm — eine geteilte Rolle ist keine Lizenz, eine etablierte Convention im Alleingang zu ändern. Den Neu-Branch-Weg habe ich genutzt, um schnelle Reviews zu bekommen und weiterarbeiten zu können. Außerdem bleibt so die Möglichkeit, die Arbeitsregeln gemeinsam zu diskutieren und den Teamworkflow eventuell etwas einfacher zu gestalten — statt das Grundproblem (Ruleset blockt Feature-Branch-Pushes) eigenmächtig zu umgehen, können wir es gemeinsam in der Rolle als Systemarchitekten besprechen, die Lucas und ich beide innehaben.
- **Alternativen (erwogen/verworfen):**
  - *Ruleset selbst auf `main` beschränken:* technisch möglich (Admin), aber es ist **Lucas' Convention/Owner-Sache** (Branch-Protection). Verworfen — keine fremden Conventions ändern (claude-sync §7).
  - *Sich selbst in die Bypass-Liste eintragen:* würde nur die eigene Person entsperren, nicht das Team. Verworfen.
  - *Auf Lucas warten:* hätte den Task blockiert. Verworfen zugunsten des sofort gangbaren Neu-Branch-Wegs.
- **Ergebnis/Status:** umgesetzt (PR #18, alte PRs/Branches ersetzt). Das **Grundproblem** (Ruleset blockt Feature-Branch-Pushes teamweit) bleibt offen → als Empfehlung an Lucas weitergegeben (Ruleset auf `main` beschränken). **Folgeentscheidung siehe #6.**

## 2026-06-22 — erinnerung-Dateien teamweit editierbar (README-Nachtrag)
- **Kontext/Task:** Team-OS / `erinnerung/`-Konvention · gemeinsame Absprache mit dem Admin (Lucas) am 2026-06-22. *(Gemeinsame Entscheidung — eigener Beitrag in der Begründung herausstellen.)*
- **Entscheidung:** `erinnerung/README.md` um einen Nachtrag ergänzt: Die Dateien in `erinnerung/` (insbesondere `stand.md`) dürfen vom gesamten Team und dessen Agenten bei Bedarf bearbeitet werden (vorher: Pflege „primär Lucas", faktisch exklusiv). Das Journal bleibt append-only.
- **Begründung:** Die `stand.md` wird bei jedem Session-Start geladen und gibt den Überblick über den Arbeitsstand — ist sie veraltet, startet das Team mit falschem Kontext. Bisher lag die Pflege laut Konvention allein bei Lucas, was einen Engpass erzeugt. Ich habe deshalb angesprochen, das zu öffnen. Wir haben uns bewusst auf eine Mischlösung geeinigt: die Hoheit/Verantwortung bleibt bei Lucas (klare Zuständigkeit), aber das Team darf Inhalte zusätzlich direkt einpflegen — das entlastet ihn und hält die Doku aktuell und konsistent. Das Journal bleibt bewusst append-only, damit parallele Beiträge konfliktfrei mergen; die Freigabe gilt also für die Überblicks-/Stand-Dateien, nicht fürs Tagebuch. Festgehalten wird das in der `erinnerung/README.md`, damit es Teil des Workflows wird und alle (inkl. Agenten beim Start) es lesen.
- **Alternativen (erwogen/verworfen):**
  - *Status quo (nur Lucas pflegt `stand.md`):* Engpass — der Stand veraltet zwischen seinen Sessions, andere können nicht nachziehen. Verworfen.
  - *Freigabe nur mündlich, ohne README-Eintrag:* für Agenten/neue Mitglieder nicht sichtbar. Verworfen — bewusst im README dokumentiert, damit es alle beim Session-Start (`uni:start`) lesen.
- **Ergebnis/Status:** umgesetzt (Commit `dc8693a`), wird mit diesem Doku-Push nach `main` gebracht.

## 2026-06-22 — Branch-Schutzeinstellung (Ruleset) auf `main` beschränken
- **Kontext/Task:** Workflow / Branch-Protection · Folge aus Entscheidung #4 und Gespräch mit Lucas über das Feature-Branch-Push-Problem. *(Gemeinsame Architekten-Entscheidung; Lucas als Owner setzt um.)*
- **Entscheidung:** Nach gemeinsamer Besprechung wird das Ruleset so angepasst, dass die „Require pull request"-Regel nur `main` betrifft statt aller Branches — Pushes/Korrekturen auf Feature-Branches sind dann wieder normal möglich.
- **Begründung:** Ich fand diesen Weg schon vorher besser, habe aber zunächst bewusst die Konvention eingehalten (siehe #4). Das eigentliche Problem ist, dass die „Require pull request"-Regel **zu breit** griff: Sie schützte *alle* Branches, obwohl nur `main` geschützt werden muss. Dadurch ließen sich eigene Feature-Branches in einem PR nach einem Review nicht mehr anpassen — jede Korrektur erzwang einen neuen Branch + PR, was unnötigen Aufwand und verwaiste Branches/PRs (Cruft) hinterließ und die Teamarbeit ausbremst. Deshalb habe ich es im Rahmen unserer geteilten Architekten-Verantwortung **nicht eigenmächtig geändert, sondern angesprochen** (vgl. #4); gemeinsam haben wir entschieden, die Regel auf `main` zu beschränken. Das ist **keine Schwächung** des Schutzes — `main` bleibt voll geschützt (PR-Pflicht, kein Direkt-Push) —, sondern entfernt nur den überschießenden Nebeneffekt auf Feature-Branches. Ergebnis: schnellere Anpassungen nach Reviews bei unverändertem Schutzprinzip für `main`.
- **Alternativen (erwogen/verworfen):**
  - *Status quo (alle Branches geschützt):* blockt Review-Korrekturen auf Feature-Branches und erzwingt Neu-Branch-Workarounds (siehe #4) inkl. Cruft. Verworfen.
  - *Einzel-Bypässe pro Person:* entsperrt nur Einzelne, nicht das Team; intransparent. Verworfen zugunsten einer sauberen teamweiten Lösung über den Owner.
- **Ergebnis/Status:** in Umsetzung durch Lucas (nach Absprache). Löst das in #4 benannte Grundproblem dauerhaft.

## 2026-06-23 — Config über typisiertes, unveränderliches Modell statt rohem dict
- **Kontext/Task:** DTB-15 (Config-Infrastructure: thresholds.json + Loader) · P0.5 · NF-05 · Enabler für DTB-38
- **Entscheidung:** Der Loader gibt die Schwellen als getypte, `frozen` Dataclasses zurück (`Thresholds` → `VereisungsSchwellen`/`PrognoseSchwellen`), nicht als rohes `dict`.
- **Begründung:** Ausschlaggebend waren für mich beide Aspekte gleichermaßen: die **Typsicherheit** für das Bewertungsmodul DTB-38, das die Schwellen konsumiert — getypter, autovervollständigbarer Zugriff statt Magic-Strings, und Schlüssel-Tippfehler fallen schon beim Laden auf statt erst in der späteren Verarbeitung. Und der **Schutz** vor versehentlichem Überschreiben der Werte zur Laufzeit: Schwellen sollen ausschließlich über die Config geändert werden (NF-05), und ein `frozen` Modell macht das technisch unmöglich, statt es nur als Konvention zu hoffen. Pydantic habe ich bewusst noch nicht genommen — für reine Zahlenfelder reichen `dataclasses` und sparen eine Abhängigkeit; **Pydantic kann genutzt werden, sobald der Umfang an Abhängigkeiten ohnehin wächst** (z. B. bei größerem Validierungs-/Schemabedarf).
- **Alternativen (erwogen/verworfen):**
  - *Rohes `dict`:* stringly-typed, keine Struktur, Magic-Strings beim Zugriff. Verworfen.
  - *Pydantic-Model:* komfortablere Validierung, aber zusätzliche Abhängigkeit/Setup; für reine Zahlenfelder reichen `dataclasses`. Zurückgestellt.
- **Ergebnis/Status:** umgesetzt, Commit `b1a60ae`.

## 2026-06-23 — Loader scheitert *laut* (ConfigError) statt stiller Defaults
- **Kontext/Task:** DTB-15 · NF-01-Geist (Fail-safe) · Selbstreview-Fund (MEDIUM: Werte-Validierung)
- **Entscheidung:** `load_thresholds` wirft `ConfigError` bei fehlender Datei, kaputtem JSON, Nicht-Objekt-Root/-Abschnitt, fehlendem Pflicht-Abschnitt/-Schlüssel **und** nicht-numerischem Wert (inkl. `bool`) — kein stiller Default.
- **Begründung:** Lautes Scheitern ist hier klar besser, **weil sofort auffällt, wenn etwas falsch läuft** — der Fehler wird beim Laden mit klarer Meldung sichtbar, statt sich als stiller Default zu tarnen und erst später in der sicherheitsrelevanten Bewertung (DTB-38) als kryptischer Fehler aufzuschlagen. Bei einer Sicherheitsanwendung ist ein Default die gefährlichere Variante: ein falsch angenommener Wert könnte eine falsche Risikobewertung erzeugen, ohne dass es jemand merkt — das widerspricht dem Fail-safe-Prinzip (NF-01). Konkret fängt die Werte-Typprüfung auch typische Eingabefehler ab, etwa die deutsche Komma-Schreibweise `"0,0"` als String statt einer Zahl.
- **Alternativen (erwogen/verworfen):**
  - *Stille Defaults bei fehlenden/ungültigen Werten:* verschleiert Konfigfehler — bei Sicherheitslogik inakzeptabel. Verworfen.
  - *Nur Struktur prüfen, Werte-Typen nicht:* eine String-Schwelle rutscht durch und bricht erst in der Arithmetik (Selbstreview-Fund M1). Verworfen.
- **Ergebnis/Status:** umgesetzt + getestet (12 Tests, 100 % Line+Branch-Coverage), Commit `b1a60ae`.

## 2026-06-23 — thresholds.json bewusst auf echte Vereisungs-Schwellen begrenzt
- **Kontext/Task:** DTB-15 · Abgrenzung zu DTB-32 (Taupunkt) / DTB-27 (Hysterese) / DTB-18 (Ingest) / DTB-33 (Prognose) — in Jira **noch nicht zugewiesen**
- **Entscheidung:** Die Config enthält nur echte Schwellen (`vereisung`-Kaskade + Prognoseschwelle). Magnus-Konstanten, Hysterese-, Datenstatus-Parameter und der Prognosehorizont wurden **wieder entfernt** (zwischenzeitlich vorgebaut).
- **Begründung:** Der saubere Schnitt war besser als der dokumentierte Vorgriff, weil wir nach dem Durchgehen der Entscheidungen sichergestellt haben, **erstmal nur die Struktur zu bauen und von den weiteren Tasks nichts falsch vorzugreifen** — etwas, das uns später nochmal ärgern oder fremde Schnittstellen vorprägen würde. Außerdem haben wir dabei **nochmal genau definiert, was wirklich Schwellenwerte sind und was hier falsch einsortiert war**: Die Magnus-Konstanten sind feste physikalische Größen und keine tunbaren Schwellen — sie gehören nicht in eine Schwellen-Config (Name = Inhalt). Hysterese- und Datenstatus-Parameter sowie der Prognosehorizont gehören zu anderen, in Jira noch nicht zugewiesenen Tasks (DTB-32/-27/-18/-33); ihre Werte jetzt mit Dummies festzulegen hätte deren Entscheidungen vorweggenommen.
- **Alternativen (erwogen/verworfen):**
  - *Eine große zentrale Config mit allen Parametern:* architektonisch denkbar, prägt aber Werte/Struktur fremder, unzugewiesener Tasks vor und mischt Kategorien (Konstanten vs. Schwellen). Verworfen nach Abgleich mit `Schwellenwerte.md` + Rücksprache.
  - *Pro-Owner-Konfigdateien jetzt anlegen:* verfrüht — die Tasks sind weder gebaut noch zugewiesen. Den Owner-Tasks überlassen.
- **Ergebnis/Status:** umgesetzt (getrimmt), Commit `b1a60ae`.

## 2026-06-23 — Test-CI neu gegen `04-Source-code/`-Layout (frischer Branch, löst PR #18 ab)
- **Kontext/Task:** DTB-11 (Test-CI) · M2 · Wiederaufnahme nach dem Repo-Root-Umzug (PR #29: Backend-Root = `04-Source-code/`). Der Alt-Branch `feat/ci-base` (PR #18) lag 50 Commits hinter `main` und nutzte das alte Root-Layout.
- **Entscheidung:** Neue `test.yml` auf einem frischen Branch ab aktueller `main` mit `working-directory: 04-Source-code`; der veraltete `feat/ci-base`/PR #18 wird abgelöst & geschlossen statt rebased.
- **Begründung:** Ausschlaggebend war die Kombination aus Sauberkeit und Konfliktrisiko: Der alte Branch lag 50 Commits hinter `main` und stammte noch aus dem Root-Layout vor dem Umzug nach `04-Source-code/` (PR #29). Ein Rebase hätte genau an dieser Layout-Grenze Konflikte erzeugt (Root-`requirements` vs. `04-Source-code/`) — Aufwand und Fehlerrisiko ohne Mehrwert, zumal der Branch-Inhalt ohnehin überholt war (Layout + E-35). Ein frischer Branch ab aktueller `main` setzt die CI direkt auf den korrekten Stand. Der veraltete PR #18 wurde deshalb abgelöst statt gerettet — der Wert lag nicht im Branch, sondern in der Aufgabe DTB-11, die auf dem neuen Layout ohnehin neu umzusetzen war.
- **Alternativen (erwogen/verworfen):**
  - *Rebase von `feat/ci-base` auf `main`:* 50-Commit-Rebase mit Layout-Konflikten (Root → `04-Source-code/`), alte Root-`requirements` müssten entfernt werden → mühsam/fehleranfällig. Verworfen.
  - *PR #18 weiterführen:* Inhalt war durch Layout-Umzug + E-35 ohnehin überholt. Verworfen.
- **Ergebnis/Status:** umgesetzt (Branch `feat/dtb-11-ci-tests`), gemergt als #50; PR #18 geschlossen, Branch gelöscht.

## 2026-06-23 — ruff-Lint als Schritt in `test.yml`
- **Kontext/Task:** DTB-11 · die Task nennt `lint.yml` ausdrücklich als optional.
- **Entscheidung:** `ruff check .` als eigener Schritt innerhalb von `test.yml` — statt separater `lint.yml` oder gar kein Lint in der CI.
- **Begründung:** Lint gehört in die CI, weil sie den Standard objektiv und automatisch für alle durchsetzt — unabhängig davon, ob jede:r lokal die Format-/Lint-Prüfung vor dem Commit laufen lässt. ruff prüft dabei nicht nur Stil, sondern mit den Regelgruppen `F`/`B` auch fehleranfällige Muster (fehlende/ungenutzte Imports, undefinierte Namen, Bug-Fallen) — ein Sicherheitsnetz vor dem Merge, nicht bloß Kosmetik. Ich habe ihn in `test.yml` gebündelt statt in eine eigene `lint.yml`, weil das einfacher ist: ein Workflow, ein Required-Check (`test`), weniger Pflege der Schutzregel. Das geht über den wörtlichen DoD hinaus (der nur `pytest --cov` fordert), kostet aber praktisch nichts (~1 s) — und liefert dafür automatische Standard-Durchsetzung.
- **Alternativen (erwogen/verworfen):**
  - *Separate `lint.yml`:* zweiter Workflow + zweiter Status-Check, mehr Verwaltung/Schutzregel-Pflege. Verworfen für den Projekt-Scope.
  - *Kein Lint in der CI (nur lokale Prüfung):* Stil-/Lint-Verstöße fallen erst lokal/im Review auf, nicht automatisch vor dem Merge. Verworfen.
- **Ergebnis/Status:** umgesetzt in `test.yml` (#50) — ein Workflow, ein Required-Check `test`.

## 2026-06-23 — CI-DB-Strategie (a): MariaDB-Service-Container
- **Kontext/Task:** DTB-11 · E-35-Hinweis im Ticket: CI-DB-Bereitstellung klären — (a) MariaDB-Service-Container im Workflow vs. (b) Coverage-Gate nur auf DB-freien Tests + Storage-Integration separat. Treiber: PyMySQL (kein SQLAlchemy). Aktuell ist die Suite vollständig DB-frei (Repository = Interface; PyMySQL-Implementierung erst DTB-28).
- **Entscheidung:** Richtung (a) — MariaDB-Service-Container im CI-Workflow, sobald DB-Tests dazukommen (DTB-28). Jetzt noch nicht eingebaut, nur als Richtung im `test.yml`-Kommentar dokumentiert.
- **Begründung:** Variante (a) hält die Hürde für alle niedrig: Ein Service-Container in der CI bedeutet, dass niemand lokal eine Datenbank installieren muss und trotzdem ein gemeinsames Coverage-Gate über die ganze Suite läuft — statt sie in „DB-frei" und „nur lokal/Pi" aufzuteilen (b), was zwei Coverage-Bereiche und mehr Abstimmung erzeugt. Den Container habe ich bewusst noch nicht eingebaut: Aktuell gibt es keinen DB-Test (das Repository ist nur ein Interface, die echte PyMySQL-Implementierung kommt erst mit DTB-28), und Infrastruktur für nicht existierende Tests vorzuhalten wäre verfrüht. Festgehalten ist die Richtung daher nur als Kommentar im Workflow, damit sie mit DTB-28 ohne erneute Diskussion umgesetzt werden kann — der Treiber ist über E-35 ohnehin gesetzt (PyMySQL, kein SQLAlchemy).
- **Alternativen (erwogen/verworfen):**
  - *(b) Coverage-Gate nur auf DB-freien Tests, Storage-Integration separat gegen Pi/lokal:* zwei getrennte Coverage-Bereiche, mehr Abstimmungsaufwand, Integration läuft nicht automatisch in der Cloud-CI. Verworfen zugunsten eines gemeinsamen Gates.
- **Ergebnis/Status:** Richtung festgelegt + dokumentiert; Umsetzung mit DTB-28.

## 2026-06-23 — Python-Matrix (3.12 + 3.14) + Aggregator-Check `test`
*(Gemeinsame Entscheidung mit Lucas — eigener Beitrag herausgestellt.)*
- **Kontext/Task:** DTB-11b (#52) · Erweiterung der festen Python-Version auf eine Matrix (3.12 + 3.14) · Wechselwirkung mit der Branch-Schutzregel (Required-Check `test`).
- **Entscheidung / eigener Beitrag:** Beim Matrix-Plan erkannt und benannt, dass eine Matrix den Check-Namen ändert (`test` → `test (3.12)`/`test (3.14)`) → der Required-Check `test` würde nie erfüllt → Merge dauerhaft blockiert. Empfohlene Lösung: Aggregator-Job mit `name: test`, der auf die Matrix wartet. Umgesetzt vom Team (Lucas, #52).
- **Begründung:** Der Kern war die Wechselwirkung zwischen Matrix und Branch-Schutzregel: Eine Python-Matrix benennt den Job-Check um (`test` → `test (3.12)`/`test (3.14)`), womit der gerade erst als Required gesetzte Check `test` nie mehr gemeldet würde — die Schutzregel hätte jeden Merge blockiert. Aus dieser Erkenntnis folgte die Entscheidung für den Aggregator-Job mit `name: test`: Er hält den Check-Namen stabil und entkoppelt ihn von der Matrix, sodass künftige Versionsänderungen die Schutzregel nicht erneut anfassen müssen — anders als bei der Alternative, wo man die Regel jedes Mal nachziehen müsste. Den Punkt habe ich beim Matrix-Plan eingebracht; umgesetzt hat ihn Lucas (#52).
- **Alternativen (erwogen/verworfen):**
  - *Branch-Schutzregel auf die Matrix-Checks umstellen (`test (3.12)`/`test (3.14)`):* funktioniert, aber die Regel muss bei jeder Matrix-Änderung nachgezogen werden. Verworfen zugunsten der Entkopplung über den Aggregator.
- **Ergebnis/Status:** Matrix + Aggregator umgesetzt (#52); Required-Check bleibt stabil `test`.

## 2026-06-23 — Poller-Fail-safe-Bug gefixt + verdeckte Pfade getestet
- **Kontext/Task:** Poller `src/ingest/` (DTB-12, Code aus PR #46) · gefunden beim Selbstreview der DTB-11-CI · NF-01 (Fail-safe).
- **Entscheidung:** Bug test-getrieben fixen — ein nicht-numerisches optionales `pressure_hpa` ließ `poll()` mit ungefangener `ValueError` crashen statt fail-safe `None`; erst ein fehlschlagender Reproducer-Test, dann der Fix (`_optional_float` in den Fail-safe-`try`), plus 7 Validierungs-Tests. Zusätzlich zwei `# pragma: no cover` entfernt und die verdeckten Fail-safe-Pfade (JSON-Parse, Repository-Fehler) mit Tests abgesichert → `poller.py` 100 % Coverage.
- **Begründung:** Der Bug stammte nicht aus meinem eigenen Code — er fiel mir während des Testens meiner CI-Arbeit (Selbstreview) auf. Ihn sofort selbst zu beheben war die zeitökonomischste Wahl: Der Fix kostete fast keine Zeit, während das bloße Melden/Übergeben an den Autor länger gedauert hätte als die Behebung selbst — einen Fail-safe-Verstoß (NF-01) wollte ich zudem nicht offen liegen lassen. Da ich ohnehin an der Stelle war, habe ich kleine zusätzliche Punkte gleich mitabgearbeitet (die zwei verdeckten Fail-safe-Pfade mit Tests abgesichert), statt sie ungetestet zu lassen.
- **Alternativen (erwogen/verworfen):**
  - *Nur melden / an den Autor übergeben statt selbst fixen:* verworfen — bei einem Fail-safe-Verstoß (NF-01) dauert das Übergeben länger als der Fix und ließe das Risiko offen.
  - *Größerer Umbau der Validierung:* verworfen zugunsten des minimalen Fix (das Feld in den bestehenden `try` ziehen).
- **Ergebnis/Status:** umgesetzt (eigener Branch), gemergt via #53/#54.

## 2026-06-23 — `_optional_status` Fehler-Muster vereinheitlicht
- **Kontext/Task:** Poller · Review-Fund (LOW: Designinkonsistenz) — `_optional_float` wirft `ValueError` (zentral gefangen), während `_optional_status` intern loggt und `None` zurückgibt: zwei Muster für denselben Zweck.
- **Entscheidung:** `_optional_status` wirft jetzt auch `ValueError` (wie die übrigen Parser) und wird zentral im Fail-safe-`try` gefangen → ein einheitliches Muster. Verhalten nach außen unverändert (fehlend → OK, defekt → Reading verworfen).
- **Begründung:** Ich habe die Inkonsistenz an der Wurzel behoben statt sie nur zu kommentieren, weil ein Kommentar den doppelten Code-Pfad nicht beseitigt — die mentale Last für den nächsten Leser bliebe. Nach der Vereinheitlichung gibt es nur noch ein Muster: alle Feld-Parser werfen bei defektem Wert `ValueError`, das zentral fail-safe behandelt wird — einheitlicher und leichter zu lesen. Wichtig war mir, dass es ein reines Refactoring bleibt: das beobachtbare Verhalten ist identisch (fehlend → OK, defekt → Reading verworfen), abgesichert durch die unveränderten Tests.
- **Alternativen (erwogen/verworfen):**
  - *Inkonsistenz belassen + nur per Kommentar erklären:* behebt die mentale Last nicht, der Doppel-Pfad bleibt. Verworfen zugunsten des Wurzel-Fix.
- **Ergebnis/Status:** umgesetzt, Verhalten durch Tests bestätigt (100 % Coverage), gemergt.

## 2026-06-23 — Poller-Härtung im vertieften Review (inkl. Korrektur der `pressure_hpa`-Entscheidung)
- **Kontext/Task:** Poller (DTB-12) · vertieftes/adversariales Review des Poller-PR (#53/#54) · ehrliche Korrektur einer früheren eigenen Entscheidung.
- **Entscheidung:** Mehrere Punkte revidiert/ergänzt: (1) `pressure_hpa` defekt → nicht mehr das ganze Reading verwerfen, sondern loggen + auf `None` setzen + Reading trotzdem speichern (revidiert die frühere „defektes optional = verwerfen"-Entscheidung); (2) `status=fault` → Reading ablehnen (Fail-safe); (3) `measured_at` nur UTC akzeptieren; (4) spezifische `RepositoryError` statt breitem `except`.
- **Begründung:** Die Korrektur folgt einer klaren Abwägung: Ein optionales Kontextfeld wie `pressure_hpa` darf die vollständigen Pflichtdaten (`surface_temp_c`/`air_temp_c`/`humidity_pct`) nicht wertlos machen — deshalb wird ein defekter Wert jetzt nur geloggt und auf `None` gesetzt, das Reading aber gespeichert, statt es komplett zu verwerfen. Im selben Zug habe ich den Poller robuster gemacht: ein vom Sensor gemeldeter Defekt (`status=fault`) führt zur Ablehnung (Fail-safe), `measured_at` wird nur als UTC akzeptiert, und Persistenzfehler fange ich gezielt über `RepositoryError` statt über ein breites `except` — präzisere Fehlerbehandlung, die keine unerwarteten Fehler verschluckt. Ehrlich festgehalten: Meine erste Lösung war bewusst defensiver (defektes optionales Feld → ganzes Reading verwerfen); das vertiefte Review hat gezeigt, dass das beim reinen Kontextfeld zu streng ist, und die Entscheidung entsprechend verfeinert.
- **Alternativen (erwogen/verworfen):**
  - *Bei „defektes optionales Feld = ganzes Reading verwerfen" bleiben:* verworfen, weil ein optionales Kontextfeld nicht die vollständigen Pflichtdaten unbrauchbar machen sollte.
- **Ergebnis/Status:** umgesetzt, gemergt via #53/#54.

## 2026-06-23 — Lokales Betriebsmodell → kein Multi-Flughafen-Backend
*(Gemeinsame Abwägung mit Lucas — eigener Beitrag herausgestellt.)*
- **Kontext/Task:** Betriebsmodell (AE-01/AE-02) · lokale Bereitstellung (native MariaDB / Pi-Hosting, E-35) vs. zentral/Cloud.
- **Entscheidung:** Ein eigenes System pro Flughafen, lokal betrieben — kein flughafenübergreifendes/zentrales Backend. Konsequenz: ein einzelnes Backend für mehrere Flughäfen ist damit nicht möglich (keine zentrale Mehr-Standort-Architektur).
- **Begründung:** In einem abwägenden Gespräch mit Lucas über die Backend-Logik wurde mir die Konsequenz klar: Weil verschiedene Flughäfen unterschiedliche Strukturen haben, lässt sich das System nicht sinnvoll flughafenübergreifend betreiben — pro Flughafen braucht es eine eigene, lokale Instanz statt eines zentralen Mehr-Standort-Backends. Mein Beitrag war das Erkennen und Benennen dieser Konsequenz (lokal ⇒ kein Multi-Flughafen-Backend), damit die Einschränkung bewusst dokumentiert ist und nicht später unbemerkt überrascht. Aus jetziger Projektsicht ist das ein bewusst akzeptierter Trade-off — der Fokus liegt auf dem einen Standort ANR; ob sich das künftig ändert, bleibt offen.
- **Alternativen (erwogen/verworfen):**
  - *Zentrales/Cloud-Betriebsmodell für mehrere Flughäfen:* würde Multi-Flughafen/Mehrmandanten ermöglichen, scheitert aber an den unterschiedlichen Strukturen der Flughäfen. Aus jetziger Sicht verworfen.
- **Ergebnis/Status:** aus jetziger Projektsicht akzeptierter Trade-off (Fokus Standort ANR); Betriebsmodell-Frage (AE-01/AE-02) langfristig offen, kann sich ändern.
