# Persönliches Entscheidungslog — Johannes Petzold (G2)
> **Erstellt am:** 2026-06-22 · **Letzte Bearbeitung:** 2026-06-27  ·  **Zeitraum:** 2026-06-22 bis 2026-06-27
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

## 2026-06-25 — Hardcode-Schwellen-Guard über AST statt Regex
- **Kontext/Task:** DTB-22 (No-Hardcode-Schwellen-Guard + CI-Gate) · Enabler für NF-05 (Schwellen müssen parametrierbar bleiben, nie als Literal im Code). Die Aufgabe schlug Regex-Beispiele (`>\s*[0-9.]`, `delta_T <= 1.0`) als Erkennungsmuster vor.
- **Entscheidung:** Erkennung über den abstrakten Syntaxbaum (AST) — `ast.Compare` mit Zahl-Operand plus die indirekten Vergleiche `operator.gt`/`math.isclose` — statt über Regex auf den Quelltext-Zeilen.
- **Begründung:** Die Aufgabenvorgaben sind für mich Vorgaben zum *Ziel*, nicht zur *Methode* — beim Ausarbeiten habe ich den Syntaxbaum als die bessere Lösung erkannt. Eine reine Textsuche kann Code nicht von Text *über* Code unterscheiden: Sie hätte einen Schwellenvergleich auch dann gemeldet, wenn er nur in einem Text, Kommentar oder Beschreibungsblock vorkommt (Fehlalarm), und über mehrere Zeilen verteilte Vergleiche übersehen. Genau solche Fehlalarme wollte ich vermeiden, weil sie sinnlos Zeit und Aufmerksamkeit kosten — und im schlimmeren Fall zu Fehlinformationen führen, die in einem sicherheitsnahen Projekt sogar Fehlentscheidungen begünstigen können. Der Syntaxbaum versteht die Struktur und schlägt nur an, wo wirklich ein Vergleich im Code steht; dieselbe Schwelle wird auch in ihrer Funktions-Schreibweise erkannt, damit man sie nicht getarnt am Wächter vorbeischreiben kann. Der etwas höhere Aufwand ist verschmerzbar, zumal ohne zusätzliche Abhängigkeit.
- **Alternativen (erwogen/verworfen):**
  - *Regex auf Textzeilen (wie skizziert):* Fehlalarme in Strings/Kommentaren/Docstrings, verpasst mehrzeilige Vergleiche. Verworfen.
  - *Externes Lint-Plugin als Abhängigkeit:* mehr Setup, Stdlib reicht. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Nicht-Schwellen-Randfälle von der Erkennung ausgenommen (Toleranzen, Wahrheitswerte)
- **Kontext/Task:** DTB-22 · Zwei Fälle sehen für eine naive Erkennung wie ein „Vergleich gegen ein Zahl-Literal" aus, sind aber keine Schwellen: die Toleranz-Parameter von `math.isclose` (`rel_tol`/`abs_tol`, z. B. `math.isclose(t_s, 0.0, rel_tol=0.01)`) und Vergleiche gegen Wahrheitswerte (`flag > True`; `bool` ist in Python technisch eine Unterart von `int`).
- **Entscheidung:** Beide werden ausdrücklich von der Schwellen-Erkennung ausgenommen — nur echte Zahl-Vergleichswerte zählen.
- **Begründung:** Eine Toleranz-/Genauigkeitsangabe und ein Wahrheitswert sind begrifflich etwas anderes als eine Schwelle. Die Schwelle ist der Wert, *gegen den* fachlich verglichen wird; eine Toleranz beschreibt nur, *wie genau* verglichen wird, und ein Wahrheitswert ist eine Ja/Nein-Aussage, kein einstellbarer Grenzwert. Solche Randfälle als Schwelle zu werten wäre fachlich falsch — und praktisch ein Fehlalarm, weil der Wächter etwas anschwärzen würde, wo gar keine konfigurationspflichtige Schwelle steht. Mir war wichtig, dass der Wächter genau bleibt und nur das meldet, was wirklich eine Schwelle ist — sonst verliert er an Glaubwürdigkeit (gleiches Motiv wie bei der Methodenwahl).
- **Alternativen (erwogen/verworfen):**
  - *Toleranzen bzw. Wahrheitswerte mitprüfen:* sichere Fehlalarme auf Nicht-Schwellen. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Grenzen der statischen Erkennung bewusst akzeptiert und dokumentiert
- **Kontext/Task:** DTB-22 · Die AST-Erkennung ist statisch und kann dem Datenfluss nicht folgen. Bauartbedingt offen bleiben u. a.: ein Literal, das erst einer Variablen zugewiesen und dann verglichen wird (`grenze = 1.0` … `if t_s > grenze`), sowie Alias-/bare-Importe (`import operator as op` → `op.gt(...)`).
- **Entscheidung:** Diese Fälle werden bewusst NICHT erkannt; sie sind als „bekannte Grenzen" im Code und im PR-Template dokumentiert und dem Code-Review als zweiter Instanz überlassen.
- **Begründung:** Eine statische Analyse hat prinzipielle Grenzen — dem Datenfluss über Variablen oder Alias-Importe hinterherzulaufen würde den Wächter deutlich aufwändiger und fehleranfälliger machen, für vergleichsweise kleinen Zusatznutzen. Für mich ist der Wächter ohnehin eine *Hilfe, kein Allheilmittel*: Er fängt die häufigen, offensichtlichen Fälle automatisch ab, der Mensch im Review bleibt die zweite Instanz für den Rest. Entscheidend war mir, diese Lücken nicht stillschweigend zu lassen, sondern ausdrücklich festzuhalten — bewusste Lücken gehören immer dokumentiert, egal ob es nur um die Nachvollziehbarkeit geht oder darum, dass man die Stelle später gezielt aus- oder umbauen will. So weiß jeder, worauf er sich beim Wächter verlassen kann und worauf nicht.
- **Alternativen (erwogen/verworfen):**
  - *Datenfluss/Alias-Fälle auch abdecken:* deutlich höhere Komplexität für geringen Nutzen, statisch ohnehin nicht vollständig. Verworfen.
  - *Lücken unkommentiert lassen:* lässt im Unklaren und erschwert spätere Erweiterung. Verworfen.
- **Ergebnis/Status:** umgesetzt + dokumentiert, gemergt als PR #73.

## 2026-06-25 — Scan bewusst auf die fachlichen Schwellen-Module begrenzt (SCAN_DIRS)
- **Kontext/Task:** DTB-22 · Der Guard scannt per Default nur `src/assessment` + `src/forecast` (über die Liste `SCAN_DIRS`), nicht das ganze `src/`; erweiterbar ohne Code-Änderung.
- **Entscheidung:** Den Scan eng auf die Module mit echten Vereisungs-/Prognose-Schwellen begrenzen; weitere Verzeichnisse nur bewusst über `SCAN_DIRS` ergänzen.
- **Begründung:** Schwellenwerte kommen fachlich nur in der Bewertung und der Prognose vor — nur dort lohnt die Prüfung. Ein globaler Scan über das ganze Projekt hätte legitime Zahlenvergleiche an anderer Stelle fälschlich angeschwärzt (etwa Status-Codes, Seiten-/Längenangaben, Indizes). Genau diese Fehlalarme wollte ich vermeiden, weil ein Wächter, der ständig grundlos anschlägt, schnell an Glaubwürdigkeit verliert und im Zweifel ignoriert oder abgeschaltet wird. Gleichzeitig habe ich den Scope nicht starr verdrahtet, sondern bewusst leicht erweiterbar gehalten: Bekommt künftig ein weiteres Modul echte Schwellen, lässt es sich an einer Stelle ergänzen, ohne den Wächter umzubauen — die Eingrenzung ist eine bewusste Vorsichtsmaßnahme gegen Fehlalarme, keine endgültige Festlegung.
- **Alternativen (erwogen/verworfen):**
  - *Global das ganze `src/` scannen:* Fehlalarme → Gate unglaubwürdig/ignoriert. Verworfen.
  - *Scope starr verdrahten:* spätere Ausweitung würde zur Umbau-Aktion. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Wächter-Tooling: schlank, überall identisch, Aufgaben sauber getrennt
- **Kontext/Task:** DTB-22 · Der Wächter läuft an drei Stellen (CI-Gate `lint-config`, optionaler lokaler pre-commit-Hook, direkter Aufruf), nutzt nur die Python-Standardbibliothek (kein `pip install`), die Scan-Pfade (`SCAN_DIRS`) werden skript-relativ aufgelöst. Die Unit-Tests des Wächters laufen nicht im Gate-Workflow, sondern im allgemeinen Test-Workflow `test.yml`.
- **Entscheidung:** (1) keine externen Abhängigkeiten; (2) die Scan-Pfade an genau einer Stelle (`SCAN_DIRS`) führen statt sie in CI und pre-commit zu duplizieren; (3) das schlanke Gate prüft nur, die Tests des Wächters laufen getrennt im Test-Workflow.
- **Begründung:** Mir ging es vor allem darum, dass es keine zweite Stelle gibt, die man pflegen muss und die unbemerkt auseinanderlaufen kann. Stünden die Scan-Pfade einmal in der CI und einmal in der pre-commit-Konfiguration, würde früher oder später jemand die eine anpassen und die andere vergessen — dann prüft der Wächter lokal etwas anderes als in der CI, ohne dass es auffällt. Eine einzige Quelle der Wahrheit schließt das aus. In dieselbe Richtung geht die Aufgabentrennung der Workflows: Jeder soll genau eine Sache tun — das Gate prüft nur auf hartcodierte Schwellen und soll als schlanker, abhängigkeitsfreier Lauf nicht das ganze Test-Framework mitschleppen; die Tests des Wächters gehören zum übrigen Test-Lauf, wo ein Defekt am Wächter den Lauf rot färbt. Zweitrangig, aber willkommen: Weil der Wächter nur die Standardbibliothek braucht, läuft er ohne Installation überall gleich — niedrige Hürde, vorhersagbar identisches Verhalten.
- **Alternativen (erwogen/verworfen):**
  - *Pfade in CI und pre-commit getrennt pflegen:* zwei Quellen → Drift-Risiko. Verworfen.
  - *Wächter-Tests im Gate mitlaufen lassen:* belastet das schlanke Gate mit dem Test-Framework, vermischt zwei Aufgaben. Verworfen.
  - *Externe Abhängigkeit/Lint-Framework:* Installation/Setup ohne Mehrwert. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Regel und Wächter-Grenzen im PR-Template sichtbar gemacht
- **Kontext/Task:** DTB-22 · Begleitend zum Wächter wurde das Pull-Request-Template ergänzt: Es erinnert in jeder neuen PR an die Regel „keine hartcodierten Schwellen, Werte aus der Konfiguration laden" und benennt die bekannten Grenzen des Wächters (nicht erkannte Fälle, die Schreibweise für begründete Ausnahmen).
- **Entscheidung:** Regel und Grenzen dort platzieren, wo Entwickler ohnehin hinschauen (PR-Template), statt sie nur im Code/Docstring zu hinterlegen.
- **Begründung:** Ein automatischer Wächter fängt viel ab, aber ein Werkzeug allein ändert kein Verhalten — Menschen müssen die Regel kennen und wissen, worauf sich der Wächter *nicht* verlässt. Im Code vergraben liest das kaum jemand; im PR-Template steht es bei jeder Änderung vor Augen. So bleibt die Regel beim Arbeiten präsent, und die Grenzen erreichen auch die, die den Wächter-Code nie öffnen — gerade weil er eine Hilfe ist und kein Allheilmittel, braucht die menschliche Ebene diese Information sichtbar. Günstige Maßnahme, große Wirkung: ein paar Zeilen Template gegen wiederkehrende Missverständnisse.
- **Alternativen (erwogen/verworfen):**
  - *Regel/Grenzen nur im Code/Docstring:* wird selten gelesen, erreicht Beitragende nicht beim Arbeiten. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Fail-closed: Was der Wächter nicht prüfen kann, färbt das Gate rot
- **Kontext/Task:** DTB-22 · Mehrere „nicht prüfbar"-Fälle werden einheitlich als Verstoß (Exit 1, rot) behandelt statt als „OK": Syntaxfehler, nicht als UTF-8 lesbare Datei, und der Fall, dass gar keine prüfbare Datei gefunden wurde. Die Invariante ist bewusst „0 prüfbare Dateien → rot", nicht „Pfad existiert → ok".
- **Entscheidung:** Jeden Fall, in dem eine Schwellen-Datei nicht zuverlässig geprüft werden konnte (nicht parsebar, nicht sauber lesbar, oder nichts Prüfbares gefunden), als Verstoß melden — nie still grün.
- **Begründung:** Der ganze Zweck des Wächters ist „keine hartcodierte Schwelle rutscht durch". Daraus folgt zwingend: „Ich konnte diese Datei nicht prüfen" muss als *Fehler* gelten, nicht als Erfolg — sonst hebelt genau das den Wächter dort aus, wo er gebraucht wird. Eine kaputte oder unleserliche Schwellen-Datei durchzuwinken wäre der gefährlichste Ausgang, weil das Problem dann unbemerkt grün durchläuft. Ich habe das bewusst an den Fail-safe-Gedanken des Projekts angelehnt (NF-01: bei Ausfall/defekten Daten nie GRÜN, sondern sicherer Zustand) — derselbe Grundsatz, auf den Wächter übertragen. Wichtig war mir auch die *richtige* Invariante: Es genügt nicht zu prüfen, ob ein Pfad existiert; entscheidend ist, ob wirklich etwas Prüfbares gefunden wurde — ein leeres/falsches Ziel darf nicht wie „alles sauber" aussehen. Und eine nicht sauber lesbare Datei prüfe ich lieber gar nicht best-effort (mit Ersatzzeichen, die Inhalt verschlucken könnten), sondern melde sie als nicht prüfbar.
- **Alternativen (erwogen/verworfen):**
  - *Nicht prüfbares still überspringen (grün):* hebelt den Zweck aus. Verworfen.
  - *Invariante „Pfad existiert → ok":* wertet leere/falsche Ziele fälschlich als sauber. Verworfen.
  - *Best-effort-Scan mit Ersatzzeichen:* könnte Inhalt verschlucken. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Fail-closed auch bei Parser-Überlast: iterativ gehärtet
- **Kontext/Task:** DTB-22 / PR #91 · Das Fail-closed-Verhalten bei nicht parsebaren Dateien wurde schrittweise vervollständigt. Zuerst fing der Wächter nur den klaren `SyntaxError`. Sehr tief verschachtelter Code lässt den Parser aber unterschiedlich abbrechen: `RecursionError` (von Lucas ergänzt), `MemoryError` („Parser stack overflowed") und ein `ValueError`/Surrogate-Fall (von mir in PR #91 gefunden). `MemoryError` wird bewusst breit gefangen.
- **Entscheidung:** Alle diese Parser-Ausfälle einheitlich fail-closed melden, statt den Wächter mit Traceback crashen zu lassen; den breiten `MemoryError`-Fall bewusst mitnehmen, auch wenn dadurch theoretisch ein echtes Speicherproblem als „nicht prüfbar" gewertet würde.
- **Begründung:** Der ehrlichste Teil dieser Aufgabe ist für mich der Prozess. Meine erste Lösung deckte nur den offensichtlichen Fall ab. Dass extrem tiefe Verschachtelung den Parser auf *mehrere* Arten überlasten kann, hätte ich vorher nicht erraten — diese Randfälle kamen erst ans Licht, weil ich und das vertiefte Review den Wächter gezielt zu brechen versucht haben. Genau das ist der Wert dieses adversarialen Testens: Solche Lücken findet man nicht durch Nachdenken allein, sondern indem man das System bewusst an seine Grenzen treibt. Jedes Mal war die Entscheidung dieselbe und folgte dem Fail-closed-Prinzip: den Fall fangen, damit der Wächter sauber rot meldet statt unkontrolliert abzustürzen. Beim `MemoryError` habe ich bewusst breit gefangen, obwohl das im Extremfall auch ein echtes Speicherproblem schlucken würde — denn bei einem Sicherheits-Gate ist „nicht prüfbar → rot" immer die sichere Richtung: Ein roter Lauf, der zu viel anzeigt, ist harmlos; ein still grüner Lauf, der etwas übersieht, ist es nicht. Die Lehre, die ich mitnehme: Robustheit an den Rändern entsteht nicht beim ersten Entwurf, sondern durch beharrliches Suchen nach dem, was schiefgehen kann — und die Fail-closed-Invariante hat über alle gefundenen Fälle gehalten.
- **Alternativen (erwogen/verworfen):**
  - *Nur `SyntaxError` fangen:* ließe die Geschwister-Fälle crashen. Verworfen, sobald bekannt.
  - *`MemoryError` nicht fangen (echtes OOM durchlassen):* wählt bei einem Sicherheits-Gate die unsichere Richtung. Verworfen zugunsten „im Zweifel rot".
- **Ergebnis/Status:** Grundlogik in PR #73, Parser-Überlast-Härtung in PR #91. Über alle Fälle verifiziert.

## 2026-06-25 — Saubere Trennung: Prüf-Logik rein, Nebeneffekte nur im CLI-Einstieg
- **Kontext/Task:** DTB-22 · Die öffentlichen Prüf-Funktionen (z. B. `pruefe_verzeichnisse`) geben ihr Ergebnis nur zurück — sie drucken nicht und verändern keinen globalen Zustand. Alles mit Nebeneffekt ist im CLI-Einstieg `main` gekapselt: Warnungen (auf stderr) und die nur *temporäre* UTF-8-Umstellung von stdout/stderr mit anschließender Wiederherstellung.
- **Entscheidung:** Prüf-Logik als reine Funktionen halten (Eingabe → Rückgabe, keine Ausgabe/Mutation); Ausgabe und temporäre Stream-Umstellung ausschließlich in `main`, inkl. Restaurierung.
- **Begründung:** Eine Funktion, die nur prüft, soll auch nur prüfen — wer sie aufruft, bekommt ein vorhersagbares Ergebnis und keine Überraschungen. Würde eine Prüf-Funktion selbst auf den Bildschirm schreiben oder gar globale Einstellungen wie das Ausgabe-Encoding dauerhaft verändern, hätte jeder spätere Aufrufer (ein Test, ein anderes Skript) unsichtbare Seiteneffekte am Hals, die schwer zu finden sind. Deshalb lebt alles, was nach außen wirkt, an genau einer Stelle: im CLI-Einstieg. Dass `main` die Konsole nur vorübergehend umstellt und danach zurücksetzt, gehört zur selben Idee — ein Werkzeug soll die Umgebung, in der es läuft, nicht bleibend verändern. Das macht den Wächter berechenbar und wiederverwendbar, statt ihn an einen bestimmten Aufrufkontext zu fesseln.
- **Alternativen (erwogen/verworfen):**
  - *Prüf-Funktionen selbst drucken lassen:* belastet reine Funktionen mit Nebeneffekten, überrascht Aufrufer. Verworfen.
  - *Stream-Umstellung dauerhaft lassen:* bleibende globale Mutation beim Aufrufer. Verworfen.
- **Ergebnis/Status:** umgesetzt, gemergt als PR #73.

## 2026-06-25 — Eine gemergte Änderung erst verifiziert, bevor ich darauf aufgebaut habe
- **Kontext/Task:** DTB-22 / PR #91 · Lucas hatte den `RecursionError`-Fang ergänzt und bereits nach `main` gemergt. Bevor ich darauf aufgebaut habe, habe ich seine Änderung adversarial nachgeprüft — und dabei zwei weitere, bis dahin ungefangene Parser-Ausfälle entdeckt (`MemoryError`, Surrogate/`ValueError`), die ich anschließend geschlossen habe.
- **Entscheidung:** Eine Änderung — auch eine bereits gemergte von jemand anderem — vor dem Weiterbauen verifizieren, statt sie als „erledigt" hinzunehmen.
- **Begründung:** Ein Fix ist für mich nicht automatisch fertig, nur weil er gemergt ist. Gerade bei einer sicherheitskritischen Invariante prüfe ich lieber zweimal nach, als etwas einfach stehen zu lassen — der kleine Mehraufwand ist nichts gegen das Risiko, auf einer Annahme aufzubauen, die gar nicht hält. Genau das hat sich hier ausgezahlt: Beim Nachprüfen von Lucas' Ergänzung kamen die weiteren Lücken überhaupt erst ans Licht; hätte ich seine Änderung blind übernommen, wären sie unbemerkt geblieben. Vertrauen in die Arbeit der anderen und eigenes Nachprüfen schließen sich für mich nicht aus — bei Sicherheitsthemen gehört die zweite Prüfung schlicht dazu.
- **Alternativen (erwogen/verworfen):**
  - *Die gemergte Änderung als erledigt hinnehmen und direkt darauf aufbauen:* hätte die weiteren Lücken übersehen. Verworfen.
- **Ergebnis/Status:** Verifikation + Folge-Härtung in PR #91.

## 2026-06-25 — SHA-Pinning der CI-Actions bewusst ausgelagert statt im Guard-PR
- **Kontext/Task:** DTB-22 · Ein Review-Befund mahnte mehrfach an, die GitHub-Actions auf feste Commit-SHAs zu pinnen statt auf Tags (`@v4`). Die Frage betrifft nicht nur den Guard-Workflow, sondern alle Workflows im Repo.
- **Entscheidung:** Das SHA-Pinning nicht im Guard-PR erledigen, sondern als repo-weite Härtung der Architektenrolle vorbehalten — Lucas und ich haben das gemeinsam so entschieden.
- **Begründung:** Mein Beitrag war, zu erkennen und zu benennen, dass dieser Befund über den Guard-PR hinausreicht: Nur einen einzelnen Workflow zu pinnen, während alle anderen auf Tags bleiben, wäre inkonsistent und würde ein flächiges Sicherheitsthema in Stückwerk zerlegen — das gehört in einen bewussten, einheitlichen Schritt, nicht beiläufig in einen unbeteiligten Feature-PR. Dazu ein ehrlicher praktischer Punkt: Die korrekten SHAs lassen sich nicht ohne Weiteres lokal verifizieren; auf einen ungeprüften SHA zu pinnen wäre selbst ein Risiko und damit das Gegenteil der beabsichtigten Härtung. Aus beidem folgte, dem Review-Druck hier *nicht* nachzugeben, sondern den richtigen Rahmen zu wählen. Weil das Thema das ganze Repo betrifft und in die geteilte Architektenverantwortung fällt, haben Lucas und ich es gemeinsam entschieden, statt dass ich es im Alleingang in meinem PR umsetze.
- **Alternativen (erwogen/verworfen):**
  - *Nur die Guard-Workflow-Actions pinnen:* inkonsistent, Stückwerk. Verworfen.
  - *Auf einen unverifizierten SHA pinnen, um den Befund schnell zu schließen:* selbst ein Risiko. Verworfen.
- **Ergebnis/Status:** als repo-weite Aufgabe der Architektenrolle (Lucas/ich) festgehalten; nicht Teil des Guard-PRs.

## 2026-06-26 — Hysterese in zwei getrennte Module geschnitten und beide in DTB-27 gebaut
- **Kontext/Task:** DTB-27, Hysterese · Schwellenwerte.md §2 · RB-01 · NF-01. Die Hysterese hat zwei Hälften: die Hochstufung, die einen Alarm erst nach anhaltender Bedingung auslöst, und die temperaturbasierte Rückstufung. Die Hochstufung war bereits umgesetzt und gehärtet. Offen war, wo die Rückstufung lebt — sie braucht Oberflächentemperatur und Kaskaden-Schwelle, während die Alarm-Engine bewusst nur die fertige Risikostufe verarbeitet.
- **Entscheidung:** Zwei getrennte Module statt eines, und beide jetzt gebaut statt eines vertagt. Die Alarm-Hysterese bleibt unverändert für das Auslösen zuständig. Die Rückstufung kommt nicht in die Alarm-Engine, sondern in ein eigenes, zustandsbehaftetes Anzeige-Modul, das die gemeldete Risikostufe für die Ampel entprellt — nach oben sofort, nach unten gedämpft — und die zustandslose Bewertung nur umhüllt. Damit hat jede Zeitkonstante genau einen Wohnort. Beide Module liegen fertig und getestet vor; offen bleibt nur der Ampel-Endpoint als Konsument.
- **Begründung:** Der entscheidende Punkt ist eine harte Randbedingung: Das Beenden eines aktiven Alarms ist rein manuell (RB-01, kein Auto-Clear). Eine automatische Rückstufung in der Alarm-Engine könnte also nur das Verbotene tun — einen aktiven Alarm selbst zurücknehmen; sie hat dort keinen erlaubten Wirkort. Ihr realer Nutzen liegt anderswo: Sie hält die Ampel um den Gefrierpunkt stabil. Es sind also zwei gegensätzlich geformte Entprellungen — der Alarm nach oben verzögert, die Anzeige nach unten stabilisiert. Beide in ein Modul zu zwingen, hätte entweder die Marge am Alarm wirkungslos gemacht oder die gehärtete Auslöse-Engine umgeschrieben und die Ampel zustandsbehaftet, mit der Gefahr, dass ein realer Vereisungsbeginn kurz als GRÜN erscheint — was der Sicherheits-Default verbietet. Die Rückstufung jetzt mitzubauen statt zu vertagen war günstig, weil das Modul klein und in sich geschlossen ist und ein Vertagen das Ampel-Flackern offen ließe.
- **Umsetzung — drei eigene Teilentscheidungen:** Erstens prüfe ich eine Herabstufung nicht über einen Rohwert-Vergleich, sondern indem ich die Bewertung gegen ein um 0,5 K in Sicherheitsrichtung verschobenes Schwellen-Set laufen lasse und mindestens fünf Minuten Stabilität verlange — so bleibt die Kaskade die einzige Quelle der Schwellen-Wahrheit, statt sie ein zweites Mal nachzubauen. Zweitens wird Unsicherheit immer sofort übernommen und nie durch die Verzögerung verdeckt, und auch die Rückkehr aus Unsicherheit gilt sofort; eine unbekannte Stufe steht außerhalb der Stufenleiter und wird nie gegen sie verrechnet. Drittens landet ein Mehrstufen-Abstieg auf der konservativen verschobenen Stufe statt auf der Rohstufe — jede weitere Stufe wird erst frei, wenn auch das verschobene Set sie zulässt, sodass die Anzeige nie unter die eigene Sicherheitsmarge springt; diesen Fall hat erst ein Review aufgedeckt.
- **Alternativen (erwogen/verworfen):**
  - *Marge in die Alarm-Engine integrieren:* verworfen — vermischt Rohwerte und fertige Risikostufe, dupliziert das Schwellen-Wissen und wirkt am Alarm wegen des manuellen Clearings kaum; das Flackern bliebe ungelöst.
  - *Alles in ein zustandsbehaftetes Modul ziehen:* verworfen — hätte die gehärtete Auslöse-Engine neu geschrieben und die Ampel zustandsbehaftet gemacht, mit der Gefahr verzögerter GRÜN-Anzeige bei realem Vereisungsbeginn.
  - *Rückstufung vertagen:* verworfen — ließe das Flackern offen und verschöbe Schwellen-nahe Logik auf den Ampel-Endpoint.
- **Ergebnis/Status:** Beide Module gebaut, getestet, gehärtet und sauber getrennt; die Bewertung bleibt zustandslos. DoD inklusive Rückstufung erfüllt. Offen: Der Ampel-Endpoint konsumiert die Anzeige-Hysterese, und die Modul-Trennung gehört noch ins zentrale Logbuch (mit Lucas abzustimmen).

## 2026-06-26 — Alarm-Auslösung als deterministische Zustandsmaschine; Quittierung ≠ Beenden
- **Kontext/Task:** DTB-27, Auslöse-Hälfte der Hysterese · RB-01 · NF-01. Die Engine entprellt einen Strom von Risikostufen und entscheidet, wann ein Alarm ausgelöst wird, ohne die zustandslose Bewertung anzufassen.
- **Entscheidung:** Eine On-Delay-Zustandsmaschine, die erst auslöst, wenn eine alarmwürdige Stufe lange genug anliegt, gemessen ab der ersten Bestätigung und tolerant gegen kurze Lücken. Die Zeit wird bei jeder Beobachtung von außen übergeben statt intern abgefragt, damit die Maschine rein und deterministisch testbar bleibt. Unsicherheit friert eine laufende Eskalation ein, eine bestätigte Entwarnung setzt sie zurück. Eine Hochstufung innerhalb der Phase ist möglich, ein Abfall löst kein automatisches Herabstufen aus. Und der einzige Weg, einen aktiven Alarm zu beenden, ist eine manuelle Aktion — eine reine Quittierung lässt ihn aktiv und darf nicht neu armen.
- **Begründung:** Determinismus zuerst — eine sicherheitskritische Auslöselogik muss ich ohne Zeit-Mocking exakt durchtesten können. Der Kern ist aber der Umgang mit Unsicherheit: Ein flackernder Sensor, der zwischen einer hohen Stufe und Unsicherheit springt, dürfte den Timer nicht ständig zurücksetzen, sonst unterdrückt die Unsicherheit selbst einen realen, anhaltenden Alarm. Also friert Unsicherheit ein statt zu resetten. Damit das nicht ewig gilt, begrenzt eine Lücken-Toleranz den Freeze: Nach einer langen Lücke beginnt ein frischer Anlauf. Eine echte Entwarnung dagegen soll den Timer ehrlich zurücksetzen — das hängt aber an einer harten Vorbedingung: Der Aufrufer muss veraltete oder defekte Daten als Unsicherheit liefern, nicht als niedrige Stufe, sonst tarnt sich ein Ausfall als Entwarnung und löscht still eine reale Eskalation. Diese Vorbedingung habe ich im Code und für den Integrationstest markiert. Kein automatisches Beenden ist RB-01 in Reinform, und Quittierung vom Beenden zu trennen verhindert, dass eine bloße Kenntnisnahme bei fortbestehender Bedingung sofort einen Zweitalarm erzeugt.
- **Alternativen (erwogen/verworfen):**
  - *Zeit intern abfragen:* verworfen — macht die Maschine zeitabhängig und nur über Uhr-Mocks testbar.
  - *Strikte Kontinuität statt Lücken-Toleranz:* verworfen — ein flackernder Sensor könnte einen realen Alarm beliebig hinauszögern; die Toleranz biast bewusst Richtung früher Warnung.
  - *Quittierung und Beenden zusammenlegen:* verworfen — verstößt gegen RB-01 und armt bei fortbestehender Bedingung fälschlich neu.
- **Ergebnis/Status:** Gebaut, getestet und über mehrere Review-Runden gehärtet. Die Vorbedingung, dass veraltete Daten als Unsicherheit ankommen müssen, ist als Auflage an die Poll-Schicht dokumentiert.

## 2026-06-26 — Asymmetrisches Fail-safe-Recovery im Alarm-Service
- **Kontext/Task:** DTB-27, der Service verbindet Engine, Persistenz und Audit-Log zu einem Auslöse-Schritt · NF-01. Die Engine dreht ihren Zustand intern auf aktiv, sobald sie auslöst — die Frage ist, was passiert, wenn der danach folgende Schreibvorgang scheitert.
- **Entscheidung:** Bewusst asymmetrisches Fehlerverhalten. Schlägt die Persistenz fehl, wird die Engine neu gearmt und der Fehler dann weitergereicht, damit die fortbestehende Bedingung erneut auslösen kann. Schlägt das Audit nach erfolgreicher Persistenz fehl, wird nicht neu gearmt — der Alarm ist real gespeichert und die Engine zu Recht aktiv; der Audit-Fehler wird gemeldet, nimmt den Alarm aber nicht zurück.
- **Begründung:** Die Engine feuert im aktiven Zustand keinen weiteren gleichrangigen Alarm. Scheitert nun die Persistenz und ich setze die Engine nicht zurück, bliebe sie aktiv ohne gespeicherten Alarm — die anhaltende Vereisung würde nie wieder auslösen, ein stiller Under-Alarm und damit genau der Fail-safe-Bruch, den das System nicht haben darf. Beim Audit ist die Lage spiegelverkehrt: Der Alarm ist persistiert und die Engine korrekt aktiv; ein fehlender Audit-Eintrag ist ein Nachvollziehbarkeits-Defizit, kein Sicherheitsproblem. Den realen Alarm dafür zurückzunehmen, würde bei fortbestehender Bedingung einen Doppel-Alarm erzeugen — der größere Schaden. Der bewusste Bias lautet also: lieber ein fehlendes Audit-Detail als ein verschluckter oder doppelter Alarm.
- **Alternativen (erwogen/verworfen):**
  - *Bei beiden Fehlern neu armen:* verworfen — beim Audit-Fehler entstünde ein Doppel-Alarm.
  - *Bei keinem Fehler neu armen:* verworfen — beim Persistenz-Fehler bliebe ein stiller Under-Alarm.
  - *Persistenz und Audit in eine Transaktion koppeln:* verworfen — das Audit ist ein eigenes, append-only geführtes Log; die Schreibpfade zu koppeln vermischt Verantwortlichkeiten ohne Sicherheitsgewinn.
- **Ergebnis/Status:** Gebaut und im Service dokumentiert; die Recovery-Naht ist mit der Engine und der Persistenz abgestimmt.

## 2026-06-26 — Alarm-Persistenz bewusst save-only als RB-01-Durchsetzung im Datenlayer
- **Kontext/Task:** DTB-27, das Alarm-Repository · RB-01 · NF-01 · E-35 (rohes PyMySQL, parametrisierte Queries). Lese- und Zustandspfade sind eigene Tickets.
- **Entscheidung:** Das Repository ist bewusst minimal — nur ein Speichern per parametrisiertem INSERT, kein Update- und kein Delete-Pfad. Das Speichern erzwingt einen aktiven Alarm; ein anderer Zustand ist ein Aufrufer-Fehler. Treiber-, CHECK- und Fremdschlüssel-Fehler werden auf eine klare Domänen-Exception heruntergebrochen statt roh durchzuschlagen. Und eine fehlende oder ungültige vergebene ID wird als Fehler behandelt, nie als Erfolg zurückgegeben.
- **Begründung:** RB-01 soll nicht nur in der Logik, sondern strukturell im Datenlayer gelten: Ein Repository ohne Update und Delete ist konstruktiv außerstande, einen aktiven Alarm automatisch zurückzunehmen — das ist die stärkste Form der Durchsetzung, nicht „wir tun es nicht", sondern „es geht hier gar nicht". Der Zwang zum aktiven Zustand verhindert, dass versehentlich ein bereits beendeter Alarm gespeichert wird und eine still falsche Historie entsteht. Die Domänen-Exception ist die Gegenseite der vorigen Entscheidung: Nur wenn ein Speicher-Fehler klar hochkommt statt roh zu crashen oder still verschluckt zu werden, kann der Service fail-safe reagieren und neu armen. Der ID-Guard schließt die letzte Lücke, weil eine ungültige ID einen anomalen Schreibpfad signalisiert. Den Zwang zum aktiven Zustand habe ich erst im Sicherheits-Review nachgeschärft.
- **Alternativen (erwogen/verworfen):**
  - *Generisches Repository mit Update und Delete:* verworfen — öffnet genau den Rücknahme-Pfad, den RB-01 verbietet, und wird hier nicht gebraucht.
  - *Speichern ohne Zustands-Check:* verworfen — ließe nicht-aktive Alarme zu und damit eine irreführende Historie.
  - *Rohe Treiberfehler durchreichen:* verworfen — der Aufrufer könnte nicht fail-safe reagieren.
- **Ergebnis/Status:** Gebaut mit abstrakter Basis, einem In-Memory-Double für DB-freie Tests und der MySQL-Implementierung, getestet inklusive der Integrationstests, die ohne erreichbare Datenbank übersprungen werden. Der reale Datenbank-Lauf ist ein Folge-Ticket.

## 2026-06-27 — Audit-Fehler: Bewertung läuft weiter, Alarm meldet sich laut (Sicherheit vor lückenlosem Protokoll)
- **Kontext/Task:** DTB-27, Verdrahtung in den Bewertungszyklus · NF-01 (Fail-safe) · NF-09 (lückenloses, append-only Audit) · FA-12 (Alarm-Audit). Jeder Zyklus schreibt zwei Audit-Ereignisse: eine Bewertungs-Protokollzeile nach jeder Bewertung und einen Alarm-Eintrag, wenn ein Alarm ausgelöst wird. Offen war: Wie reagiert das System, wenn das Audit-Log fehlschlägt — den sicherheitsrelevanten Vorgang abbrechen (für ein lückenloses Protokoll) oder weiterlaufen lassen?
- **Entscheidung:** Asymmetrisch, abgestuft nach Sicherheitsrelevanz. Schlägt das **Bewertungs-Audit** fehl, läuft der Zyklus weiter — der Fehler wird nur protokolliert, die Bewertung selbst steht trotzdem. Schlägt das **Alarm-Audit** fehl, wird das als eigener, lauter Fehler nach oben gemeldet (mit der ID des trotzdem gespeicherten Alarms, auf Fehler-Logstufe), aber der Alarm bleibt gültig und aktiv. In keinem Fall blockiert ein Audit-Fehler den eigentlichen Sicherheits-Output.
- **Begründung:** Beim Zielkonflikt zwischen „nie eine unsichere Lücke" (NF-01) und „lückenloses Protokoll" (NF-09) hat die Sicherheit Vorrang. Würde ich den Zyklus bei einem Audit-Fehler abbrechen, könnte ein kaputtes Logging das Erkennen oder Anzeigen einer realen Vereisung verhindern — das Protokoll-Ziel würde das Sicherheits-Ziel aushebeln, genau verkehrt herum. Deshalb darf ein fehlendes Protokoll nie den Bewertungs- oder Alarm-Output verhindern. Die Asymmetrie folgt der Schwere des Defizits: Eine fehlende Bewertungs-Protokollzeile ist ein reines Nachvollziehbarkeits-Defizit — nur protokollieren und weiter. Ein gespeicherter Alarm ohne Protokoll-Eintrag ist gravierender: Der Alarm existiert real, aber seine Entstehung ist nicht belegt; das muss laut und mit Bezug zum konkreten Alarm gemeldet werden, damit es jemandem auffällt, statt unterzugehen. Genau deshalb „laut" (Fehler nach oben, mit Alarm-ID, auf Fehler-Stufe) statt einer beiläufigen Warnung.
- **Alternativen (erwogen/verworfen):**
  - *Audit und Vorgang in einer Transaktion koppeln (alles-oder-nichts):* verworfen — dann verhindert ein Audit-Ausfall den Sicherheits-Output (NF-01-Bruch); zudem ist das Audit ein eigenes, append-only geführtes Log, das bewusst nicht an den fachlichen Schreibpfad gekoppelt ist.
  - *Beide Audit-Fehler gleich behandeln, beide nur protokollieren:* verworfen — ein gespeicherter Alarm ohne Beleg ist gravierender als eine fehlende Bewertungszeile und verdient eine eigene, laute Meldung mit Alarm-Bezug.
  - *Beide Audit-Fehler gleich behandeln, beide hart melden:* verworfen — würde den häufigeren, unkritischen Bewertungs-Audit-Fehler unnötig zum lauten Vorfall eskalieren.
- **Ergebnis/Status:** Umgesetzt und getestet (je ein Fehlerfall für beide Audit-Pfade). Bewusste Abwägung Sicherheit (NF-01) vor lückenlosem Protokoll (NF-09); in keinem Pfad wird ein Audit-Fehler still verschluckt (immer mindestens protokolliert). **Offen:** die zentrale Architektur-Notiz zu dieser Abwägung mit Lucas abstimmen.
