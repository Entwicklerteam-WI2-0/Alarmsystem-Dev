# Persönliches Entscheidungslog — Johannes Petzold (G2)
> **Erstellt am:** 2026-06-22 · **Letzte Bearbeitung:** 2026-06-22
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
