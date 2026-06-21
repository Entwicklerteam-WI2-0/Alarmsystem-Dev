# Review: Feature-Planning-Group (FPG) Skills für G2-Backend

> **Ziel:** Bewertung der installierten Feature-Planning-Skills für den Einsatz im Backend-Team G2 (`Alarmsystem-Dev`).
> **Durchgeführt:** 2026-06-21
> **Quellen:** Kimi Code CLI-Dokumentation (Skills/Plugins/Hooks) + installierte Skills unter `~/.kimi-code/skills/`.
> **Kontext:** `Alarmsystem-Dev` · Backend-Gruppe G2 · Vereisungserkennung ANR

---

## 1. Zusammenfassung

Ausgehend von der BLP-Install wurden **14 Feature-/Architektur-Planungs-Skills** in Kimi Code CLI installiert. Dieses Review bewertet diese Skills nach ihrer **Eignung für das G2-Backend-Projekt** und gibt Empfehlungen, welche Skills im regulären G2-Workflow (WP2 Planung, WP3 Implementierung mit TDD, WP6 Review) verwendet werden sollten.

**Kernbefund:**
- Die installierten Skills decken die gesamte Planungs-Pipeline ab: **Idee → Design → Spec → PRD → Slicing → Tasks → TDD-Implementierung**.
- Für G2-Backend sind besonders relevant: `feature-design-assistant`, `feature-plan-architect`, `vertical-slice-planning-1`, `tdd-feature-planner`, `workflow-planner`.
- `spec-proposal-creation` und `spec-driven-planning` sind methodisch wertvoll, aber der chinesische Skill-Body (`skilled-spec-cn`) erschwert die Nutzung im deutschen G2-Kontext.
- `prd-workflow-feature-planner` ist sehr umfangreich (352 Zeilen) und eher für Produkt-/PRD-Workflows geeignet; im reinen Backend-Feature-Planning ist er overhead-lastig.

---

## 2. Bewertungskriterien

| Kriterium | Gewichtung | Frage |
|---|---|---|
| **Backend-Relevanz** | Hoch | Passt der Skill zum G2-Scope (Ingest, Persistenz, Bewertungslogik, API)? |
| **Sicherheitskritikalität** | Hoch | Unterstützt der Skill RB-01 (keine automatische Freigabe) und NF-01 (Fail-safe)? |
| **G2-Workflow-Integration** | Hoch | Lässt sich der Skill in WP2/WP3/WP6 integrieren? |
| **Einfachheit** | Mittel | Ist der Skill für das ~2.-Sem.-Team nutzbar, ohne Überforderung? |
| **Deutsche Sprache** | Mittel | Kann der Skill im deutschen Projekt-Kontext genutzt werden? |
| **Redundanz** | Niedrig | Überschneidet sich der Skill stark mit bereits vorhandenen G2-Skills (`plan`, `feature-dev`, `blueprint-spec`)? |

---

## 3. Skill-Bewertungen

### 3.1 `feature-planning`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Generisch für alle Feature-Requests, auch Backend |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Unterstützt strukturierte Planung, reduziert Fehlplanung |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | Passt direkt in WP2 (Planung) |
| Einfachheit | ⭐⭐⭐⭐⭐ | Klare Schritt-für-Schritt-Anleitung |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englischer Skill-Body, aber einfach verständlich |
| Redundanz | ⭐⭐⭐ | Überschneidung mit `feature-dev` und `plan` |

**Empfehlung:** Standard-Skill für alle neuen Backend-Features. Vorzugsweise vor `feature-dev` verwenden.

---

### 3.2 `feature-design-assistant`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Codebase-Exploration + Design-Dialog passen zu API-/Modul-Design |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Erzwingt bewusste Design-Entscheidungen vor Coding |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | Ideal für WP2 vor Architektur-Entscheidungen |
| Einfachheit | ⭐⭐⭐⭐ | Strukturierter Dialog, erfordert aber aktive User-Beteiligung |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch, klar |
| Redundanz | ⭐⭐⭐ | Ergänzt `plan` und `feature-dev` |

**Empfehlung:** Verwenden, wenn ein Feature Design-Entscheidungen erfordert (z. B. API-Naht G1/G3, Bewertungslogik-Module).

---

### 3.3 `feature-plan-architect`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Backend-Architektur, APIs, Microservices, Distributed Systems |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Hilft bei Architektur-Entscheidungen mit Blick auf Robustheit |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP2 + Architektur-Entscheidungslogbuch |
| Einfachheit | ⭐⭐⭐ | Eher für erfahrenere Teammitglieder/Architekten |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐⭐ | Ergänzt `architecture-decision-records` und `mp-codebase-design` |

**Empfehlung:** Für Lucas/Johannes als Architekten vorgesehen. Nicht für jedes kleine Feature, sondern für API-Design, Datenmodell, Schnittstellen-Entscheidungen.

---

### 3.4 `spec-proposal-creation`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐ | Generisch anwendbar, aber nicht Backend-spezifisch |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Strukturierte Specs erhöhen Nachvollziehbarkeit |
| G2-Workflow-Integration | ⭐⭐⭐⭐ | WP2 Spec-First |
| Einfachheit | ⭐⭐⭐ | Chinesischer Body erschwert Nutzung im deutschen Kontext |
| Deutsche Sprache | ⭐⭐ | Chinesisch |
| Redundanz | ⭐⭐ | Starke Überschneidung mit `spec-driven-dev` und `sdd` |

**Empfehlung:** Methodisch wertvoll, aber aufgrund der Sprache nur bedingt empfohlen. Stattdessen `spec-driven-dev` oder `sdd` bevorzugen.

---

### 3.5 `spec-driven-planning`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐ | Generisch anwendbar |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Test- & Validations-First passt zu NF-01 |
| G2-Workflow-Integration | ⭐⭐⭐⭐ | WP3 Implementierung nach Spec |
| Einfachheit | ⭐⭐⭐ | Chinesischer Body |
| Deutsche Sprache | ⭐⭐ | Chinesisch |
| Redundanz | ⭐⭐ | Überschneidung mit `spec-driven-dev`, `sdd`, `tdd-feature-planner` |

**Empfehlung:** Nur verwenden, wenn das Team mit der chinesischen Dokumentation arbeiten kann. Alternativ `spec-driven-dev` + `tdd-feature-planner`.

---

### 3.6 `spec-driven-pattern-capture`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Clean Architecture, Hexagonal, DDD direkt für Backend |
| Sicherheitskritikalität | ⭐⭐⭐ | Architektur-Muster indirekt relevant für Robustheit |
| G2-Workflow-Integration | ⭐⭐⭐⭐ | WP2 Architektur-Design |
| Einfachheit | ⭐⭐⭐ | Muster-Wissen erforderlich |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐⭐⭐ | Gutes Ergänzungsskill, wenig Redundanz |

**Empfehlung:** Für Architektur-Diskussionen und ADRs nutzen, wenn über Muster entschieden wird.

---

### 3.7 `prd-workflow-feature-planner`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐ | PRD-Fokus, eher Produkt als Backend |
| Sicherheitskritikalität | ⭐⭐⭐ | PRD kann Sicherheitsanforderungen erfassen |
| G2-Workflow-Integration | ⭐⭐⭐ | Eher früh im Projekt, nicht im täglichen Backend-Betrieb |
| Einfachheit | ⭐⭐ | Sehr umfangreich (352 Zeilen), viele Templates |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐ | Überschneidung mit `mp-to-prd`, `pmai-spec-prd` |

**Empfehlung:** Für große Features mit externem/Product-Kontext. Im reinen Backend-Feature-Flow eher `feature-design-assistant` + `feature-planning` bevorzugen.

---

### 3.8 `tdd-feature-planner`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | TDD zentral für Bewertungslogik (Coverage ≥ 80 %) |
| Sicherheitskritikalität | ⭐⭐⭐⭐⭐ | RED-GREEN-REFACTOR erhöht Vertrauen in kritische Logik |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP3 TDD |
| Einfachheit | ⭐⭐⭐⭐⭐ | Klarer TDD-Zyklus |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐ | Ergänzt `tdd-workflow` und `python-testing` |

**Empfehlung:** **Pflicht-Skill für die Bewertungslogik und alle sicherheitskritischen Module.**

---

### 3.9 `workflow-planner` (planning-with-files)

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐ | Persistente Plan-Dateien helfen bei langen Features |
| Sicherheitskritikalität | ⭐⭐⭐ | Kein direkter Einfluss |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP2/WP3 für Multi-Session-Features |
| Einfachheit | ⭐⭐⭐⭐ | Markdown-basiert, leicht verständlich |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐⭐ | Ergänzt `feature-planning` und `task-planner` |

**Empfehlung:** Für Features, die über mehrere Sessions/Sitzungen laufen. Hilft bei Kontinuität im Team.

---

### 3.10 `task-planner` (task-execution-engine)

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Task-Listen direkt für Backend-Implementierung |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Strukturierte Abarbeitung reduziert Fehler |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP3 Implementierung |
| Einfachheit | ⭐⭐⭐⭐ | Markdown-Checkbox-System |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐⭐ | Ergänzt `workflow-planner` |

**Empfehlung:** Nach `feature-planning`/`vertical-slice-planning-1` verwenden, um Tasks auszuführen.

---

### 3.11 `vertical-slice-planning-1`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Vertikale Slices ideal für Backend-Features (z. B. Endpoint → DB → Bewertung) |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Jeder Slice end-to-end testbar |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP2 Planung + WP3 TDD |
| Einfachheit | ⭐⭐⭐⭐⭐ | Klare Heuristiken |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐⭐ | Ergänzt `citypaul-planning` |

**Empfehlung:** **Standard-Skill für die Aufteilung größerer Backend-Features.**

---

### 3.12 `spec-driven-dev`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐⭐ | Requirements → Design → Tasks → Implementation |
| Sicherheitskritikalität | ⭐⭐⭐⭐⭐ | Spec vor Code, ideal für kritische Logik |
| G2-Workflow-Integration | ⭐⭐⭐⭐⭐ | WP2 + WP3 |
| Einfachheit | ⭐⭐⭐⭐⭐ | Klarer Ablauf |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐ | Gute Ergänzung zu `feature-planning` |

**Empfehlung:** **Primärer Spec-Driven-Development-Skill für G2.**

---

### 3.13 `sdd`

| Aspekt | Bewertung | Begründung |
|---|---|---|
| Backend-Relevanz | ⭐⭐⭐⭐ | GitHub Spec-Kit, generisch |
| Sicherheitskritikalität | ⭐⭐⭐⭐ | Executable specs |
| G2-Workflow-Integration | ⭐⭐⭐⭐ | WP2 + WP3 |
| Einfachheit | ⭐⭐⭐⭐ | Etwas umfangreicher als `spec-driven-dev` |
| Deutsche Sprache | ⭐⭐⭐⭐⭐ | Englisch |
| Redundanz | ⭐⭐ | Ergänzt `spec-driven-dev` |

**Empfehlung:** Für Teams, die GitHub Spec-Kit nutzen wollen. Ansonsten `spec-driven-dev` bevorzugen.

---

## 4. Empfohlener G2-Workflow mit FPG-Skills

| Phase | Empfohlener Skill | Zweck |
|---|---|---|
| **WP2 Planung** | `feature-design-assistant` | Idee → Design-Dialog |
| **WP2 Planung** | `feature-planning` | Design → Task-Plan |
| **WP2 Planung** | `vertical-slice-planning-1` | Plan → vertikale Slices |
| **WP2 Architektur** | `feature-plan-architect` | Backend-/API-Architektur |
| **WP2 Architektur** | `spec-driven-pattern-capture` | Muster-Auswahl (Clean/Hexagonal/DDD) |
| **WP2 Spec** | `spec-driven-dev` | Requirements/Design/Tasks-Doku |
| **WP3 Implementierung** | `tdd-feature-planner` | RED-GREEN-REFACTOR |
| **WP3 Implementierung** | `task-planner` | Tasks ausführen |
| **WP3 Tracking** | `workflow-planner` | Persistente Plan-Dateien |
| **WP6 Review** | `feature-plan-architect` + `tdd-feature-planner` | Architektur- & Test-Review |

---

## 5. Konflikte & Redundanzen

| Konflikt | Empfehlung |
|---|---|
| `spec-proposal-creation` / `spec-driven-planning` (chinesisch) vs. `spec-driven-dev` / `sdd` (englisch) | Englische Varianten bevorzugen |
| `prd-workflow-feature-planner` vs. `feature-planning` | `feature-planning` für Backend; PRD-Skill nur bei Product-Kontext |
| `feature-plan-architect` vs. `mp-codebase-design` | Beide nutzbar; `feature-plan-architect` für Backend-Architektur, `mp-codebase-design` für Modul-Design |
| `vertical-slice-planning-1` vs. `citypaul-planning` | `vertical-slice-planning-1` hat konkretere Heuristiken; `citypaul-planning` als Alternative |

---

## 6. Fazit & Handlungsempfehlung

- **Installation:** Alle FPG-Skills sind installiert und einsatzbereit (nach Kimi-Neustart).
- **Empfohlener Kern-Stack für G2:**
  1. `feature-design-assistant`
  2. `feature-planning`
  3. `vertical-slice-planning-1`
  4. `feature-plan-architect`
  5. `spec-driven-dev`
  6. `tdd-feature-planner`
  7. `task-planner`
  8. `workflow-planner`
- **Optional/ergänzend:** `spec-driven-pattern-capture`, `sdd`, `prd-workflow-feature-planner`.
- **Nicht empfohlen für G2:** `spec-proposal-creation` und `spec-driven-planning` aufgrund des chinesischen Skill-Bodys — stattdessen `spec-driven-dev` verwenden.

Nächster Schritt: Nach Kimi-Neustart die empfohlenen Skills mit `/skill:<name>` in einem kleinen Test-Feature aktivieren und das Vorgehen im Team-Meeting abstimmen.
