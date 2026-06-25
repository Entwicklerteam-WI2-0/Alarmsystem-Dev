"""DTB-22: Guard gegen hartcodierte Schwellenwerte (Enabler, NF-05).

Scannt die fachlichen Schwellen-Module auf numerische Literale in Vergleichen
(z. B. `t_s > 1.0`, `delta_t <= 1.0`). Vereisungs-/Prognose-Schwellen MÜSSEN über
`config/` geladen werden (DTB-15 `src/config/loader.py`) und dürfen nicht im Code
stehen — sonst lassen sich die noch ausstehenden G1-Finalwerte nicht ohne
Code-Änderung austauschen.

Erkennung über den **AST** (`ast.Compare` mit Zahl-Literal-Operand sowie indirekte
Vergleichs-Calls `operator.gt`/`math.isclose`) statt über Regex auf Textzeilen. Das
deckt die ursprünglichen DoD-Beispiele (`>\\s*[0-9.]`, `<\\s*[0-9.]`, `delta_T <= 1.0`)
semantisch ab und ist robust gegen Zeilenumbrüche, Strings, Kommentare und Docstrings.

**Fail-closed:** Eine nicht parsebare Datei (echter SyntaxError) wird als Verstoß
gemeldet (Gate rot), statt still „OK" zu liefern — ein Schwellen-Modul, das nicht
geprüft werden kann, darf nicht grün durchrutschen. BOM-Dateien werden über
`utf-8-sig` korrekt gelesen.

Aufruf (aus 04-Source-code/):
    python tools/check_hardcoded_thresholds.py            # Default-Verzeichnisse
    python tools/check_hardcoded_thresholds.py src/ingest # eigene Verzeichnisse

Exit-Code 0 = sauber, 1 = Verstoß gefunden. Wird von der GitHub-Action
`.github/workflows/lint-config.yml` und optional von pre-commit aufgerufen.

Begründete Ausnahmen: `# noqa: hardcoded-threshold` auf die **Vergleichszeile**
(Zeile des linken Operanden) setzen.

Bekannte Grenzen (bewusst). Zwei Ursachen:
(a) Datenfluss — statisch nicht auflösbar:
  - Literal erst einer Variable/Modulkonstante zugewiesen, dann verglichen
    (`grenze = 1.0` / `THRESHOLD: float = 1.0` … `if t_s > grenze`).
  - Literal als Funktionsargument/Default/Dict-Wert oder Clamp (`max(t_s, 0.0)`,
    `def f(g=1.0)`, `{"rot": 1.0}`, `min(1.0, max(0.0, p))`) — kein Vergleich.
(b) Strukturell — kein direkter `ast.Compare`-Operand:
  - Literale in Sammlungen (`if stufe in (0.0, 1.0)`) und match/case-Muster (`case 1.0:`).
  - Indirekte Vergleiche nur als `operator.gt(...)`/`math.isclose(...)` in unveränderter
    Modul-Schreibweise erkannt — nicht bei Alias (`import operator as op` → `op.gt(...)`),
    bare-Import (`from operator import gt`) oder Fremd-Libs (`np.greater`).
  - Verkettete Vergleiche (`0.0 < t_s < 1.0`) zählen als ein Befund (ein Compare-Knoten).
  - Nur UTF-8-Quellen; abweichende PEP-263-`coding:`-Deklarationen werden fail-closed gemeldet.
Diese Fälle bleiben dem Code-Review (zweite Instanz) überlassen. Legitime Nicht-Schwellen-
Vergleiche (Längen/Indizes/Status, z. B. `len(x) > 0`) mit dem noqa-Marker entschärfen —
relevant erst bei Erweiterung von SCAN_DIRS auf ingest/api.
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# Bewusst nur die Module, in denen Schwellen-Vergleiche fachlich vorkommen
# (Bewertungskaskade + Prognose). Ein globaler Scan würde Status-Codes, Pagination
# und Indizes als Fehlalarm treffen. Erweiterbar (z. B. ("src/assessment",
# "src/forecast", "src/ingest")) ohne weitere Code-Änderung — siehe DTB-22-Scope.
SCAN_DIRS: tuple[str, ...] = ("src/assessment", "src/forecast")

# Wer einen Wert bewusst erlaubt, hängt diesen Marker als Kommentar an die Zeile.
ERLAUBT_MARKER = "noqa: hardcoded-threshold"

# Vergleichs-Hilfsfunktionen ohne Operator-Zeichen (Modul, Funktionsname) — ein
# `operator.gt(t_s, 1.0)` ist genauso ein Schwellen-Vergleich wie `t_s > 1.0`.
_VERGLEICHS_FUNKTIONEN = {("operator", name) for name in ("gt", "ge", "lt", "le", "eq", "ne")} | {
    ("math", "isclose")
}


@dataclass(frozen=True)
class Verstoss:
    """Ein gefundenes Schwellen-Literal in einem Vergleich (oder eine nicht prüfbare Datei)."""

    datei: str
    zeile: int
    inhalt: str
    grund: str


def _ist_zahl_literal(knoten: ast.AST) -> bool:
    """True, wenn der Knoten ein numerisches Literal ist (auch mit Vorzeichen, ohne bool)."""
    if isinstance(knoten, ast.Constant):
        return isinstance(knoten.value, (int, float)) and not isinstance(knoten.value, bool)
    if isinstance(knoten, ast.UnaryOp) and isinstance(knoten.op, (ast.UAdd, ast.USub)):
        return _ist_zahl_literal(knoten.operand)
    return False


# Keyword-Argumente, die Toleranzen sind (math.isclose) — keine Schwellen, daher ignoriert.
_TOLERANZ_KWARGS = frozenset({"rel_tol", "abs_tol"})


def _ist_vergleichs_call(knoten: ast.AST) -> bool:
    """True für `operator.gt(...)`/`math.isclose(...)` mit einem Zahl-Literal als Vergleichswert.

    Positions- UND Keyword-Argumente zählen (`math.isclose(a=t_s, b=0.0)`), nur die
    Toleranz-Keywords `rel_tol`/`abs_tol` werden ausgenommen — sie sind keine Schwellen.
    """
    if not isinstance(knoten, ast.Call):
        return False
    fn = knoten.func
    if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)):
        return False
    if (fn.value.id, fn.attr) not in _VERGLEICHS_FUNKTIONEN:
        return False
    # kw.arg ist None bei **kwargs-Entpackung — diese überspringen (kein Vergleichswert).
    kandidaten = [
        *knoten.args,
        *(
            kw.value
            for kw in knoten.keywords
            if kw.arg is not None and kw.arg not in _TOLERANZ_KWARGS
        ),
    ]
    return any(_ist_zahl_literal(arg) for arg in kandidaten)


def _hat_marker(kommentar: str) -> bool:
    """True, wenn der Kommentar den Marker als abgegrenztes Token trägt (nicht z. B. `…-OFF`)."""
    idx = kommentar.find(ERLAUBT_MARKER)
    if idx == -1:
        return False
    naechstes = kommentar[idx + len(ERLAUBT_MARKER) : idx + len(ERLAUBT_MARKER) + 1]
    return naechstes == "" or not (naechstes.isalnum() or naechstes in "-_")


def _noqa_zeilen(quelltext: str, dateiname: str) -> set[int]:
    """Zeilennummern mit dem Escape-Marker — nur echte Kommentare (nicht Strings)."""
    zeilen: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(quelltext).readline):
            if tok.type == tokenize.COMMENT and _hat_marker(tok.string):
                zeilen.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        # Marker-Erkennung entfällt (unvollständiger Tokenstrom) — sichtbar machen, sonst
        # greift ein korrektes # noqa unbemerkt nicht und es gibt einen Fehlalarm ohne Grund.
        print(f"WARNUNG: {dateiname}: noqa-Marker nicht lesbar (Tokenisierung unvollständig).")
    return zeilen


def _ist_schwellen_treffer(knoten: ast.AST) -> bool:
    """True, wenn der Knoten ein Vergleich gegen ein Zahl-Literal ist (direkt oder indirekt)."""
    if isinstance(knoten, ast.Compare):
        return any(_ist_zahl_literal(op) for op in [knoten.left, *knoten.comparators])
    return _ist_vergleichs_call(knoten)


def finde_verstoesse(quelltext: str, dateiname: str) -> list[Verstoss]:
    """Findet Schwellen-Literale in Vergleichen via AST.

    Erkennt direkte Vergleiche (`ast.Compare` mit Zahl-Operand) und indirekte
    Vergleichs-Calls (`operator.gt`/`math.isclose`). Strings, Kommentare und
    Docstrings lösen keinen Fehlalarm aus; `# noqa: hardcoded-threshold` auf der
    Vergleichszeile unterdrückt. Nicht parsebarer Code wird fail-closed gemeldet.
    """
    quelltext = quelltext.lstrip("\ufeff")  # evtl. BOM entfernen (utf-8-sig deckt Dateien ab)
    try:
        baum = ast.parse(quelltext)
    except SyntaxError as exc:
        # Fail-closed: eine nicht prüfbare Schwellen-Datei darf das Gate nicht grün lassen.
        return [
            Verstoss(
                datei=dateiname,
                zeile=exc.lineno or 1,
                inhalt="<Datei nicht parsebar — Schwellen-Check fail-closed>",
                grund="Datei nicht parsebar (SyntaxError) — Gate fail-closed",
            )
        ]

    noqa = _noqa_zeilen(quelltext, dateiname)
    quellzeilen = quelltext.splitlines()
    roh: list[tuple[int, int, Verstoss]] = []  # (zeile, spalte) für stabile Sortierung

    for knoten in ast.walk(baum):
        if not _ist_schwellen_treffer(knoten):
            continue
        nr = knoten.lineno
        if nr in noqa:  # Marker auf der Vergleichszeile (Zeile des linken Operanden)
            continue
        inhalt = quellzeilen[nr - 1] if 0 <= nr - 1 < len(quellzeilen) else ""
        roh.append(
            (
                nr,
                knoten.col_offset,
                Verstoss(
                    datei=dateiname,
                    zeile=nr,
                    inhalt=inhalt,
                    grund="numerisches Schwellen-Literal in Vergleich — über config/ laden",
                ),
            )
        )

    roh.sort(key=lambda t: (t[0], t[1]))
    return [verstoss for _, _, verstoss in roh]


def _klassifiziere_ziele(
    ziele: Iterable[str | Path],
) -> tuple[list[Path], list[str], list[str]]:
    """Ein Durchlauf: (prüfbare `.py`-Dateien dedupliziert, fehlende Ziele, ignorierte Ziele).

    Klassifiziert jedes Ziel mit einer stat-Runde (`is_file`/`is_dir`) statt zusätzlich
    `exists()`: `.py`-Datei → prüfbar; Verzeichnis → rekursiv; existierende Nicht-`.py`-Datei
    → „ignoriert" (sichtbar machen, nicht still verschlucken); sonst → „fehlend".
    """
    dateien: list[Path] = []
    fehlend: list[str] = []
    ignoriert: list[str] = []
    for ziel in ziele:
        pfad = Path(ziel)
        if pfad.is_file():
            if pfad.suffix == ".py":
                dateien.append(pfad)
            else:
                ignoriert.append(str(ziel))  # existiert, ist aber keine .py-Datei
        elif pfad.is_dir():
            dateien.extend(sorted(pfad.rglob("*.py")))
        else:
            fehlend.append(str(ziel))  # existiert nicht (weder Datei noch Verzeichnis)
    # Überlappende Ziele (Datei zweimal, oder Datei + ihr Verzeichnis) deduplizieren,
    # damit kein Verstoß doppelt gemeldet/gezählt wird; Reihenfolge bleibt erhalten.
    eindeutig: dict[Path, Path] = {}
    for datei in dateien:
        eindeutig.setdefault(datei.resolve(), datei)
    return list(eindeutig.values()), fehlend, ignoriert


def _py_dateien(ziele: Iterable[str | Path]) -> list[Path]:
    """Prüfbare `.py`-Dateien aus den Zielen (Datei direkt, Verzeichnis rekursiv, dedupliziert)."""
    return _klassifiziere_ziele(ziele)[0]


def pruefe_dateien(dateien: Iterable[Path]) -> list[Verstoss]:
    """Scannt eine Liste von `.py`-Dateien auf Schwellen-Literale."""
    verstoesse: list[Verstoss] = []
    for py_datei in dateien:
        # utf-8-sig entfernt eine evtl. BOM (Windows-Editoren); errors="replace" sorgt
        # dafür, dass eine einzelne defekte Datei das Gate nicht mit Traceback abbricht.
        try:
            text = py_datei.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            # Datei nicht lesbar (z. B. PermissionError) -> fail-closed statt Traceback:
            # eine nicht prüfbare Schwellen-Datei darf das Gate nicht grün lassen.
            verstoesse.append(
                Verstoss(
                    datei=str(py_datei),
                    zeile=1,
                    inhalt=f"<Datei nicht lesbar: {exc.__class__.__name__}>",
                    grund="Datei nicht lesbar — Gate fail-closed",
                )
            )
            continue
        verstoesse.extend(finde_verstoesse(text, str(py_datei)))
    return verstoesse


def pruefe_verzeichnisse(verzeichnisse: Iterable[str | Path]) -> list[Verstoss]:
    """Scannt alle `.py`-Dateien unter den angegebenen Zielen (Verzeichnisse oder Dateien)."""
    return pruefe_dateien(_py_dateien(verzeichnisse))


def _melde_verstoesse(verstoesse: list[Verstoss]) -> None:
    """Druckt den FEHLER-Block für `main` — mit auf die Fund-Art zugeschnittenem Rat."""
    print("FEHLER: hartcodierte Schwellen oder nicht prüfbare Dateien (NF-05 — config/ nutzen):\n")
    for verstoss in verstoesse:
        print(f"  {verstoss.datei}:{verstoss.zeile}: {verstoss.inhalt.strip()}")
    print(f"\n{len(verstoesse)} Verstoß/Verstöße.")
    # Rat getrennt nach Fund-Art — für eine nicht prüfbare Datei ist „config/ laden" falsch.
    # Marker „fail-closed" im Grund = nicht prüfbare Datei (Syntax/Encoding/Lesefehler).
    if any("fail-closed" not in v.grund for v in verstoesse):
        print(
            f"  → Schwellen über config/ laden (src/config/loader.py) oder begründete Ausnahme "
            f"mit '# {ERLAUBT_MARKER}' auf der gemeldeten Zeile markieren "
            f"(bei mehrzeiligem Vergleich: erste Zeile)."
        )
    if any("fail-closed" in v.grund for v in verstoesse):
        print(
            "  → Nicht prüfbare Dateien beheben (Syntax/Encoding/Berechtigung) — Gate fail-closed."
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI-Einstieg: Exit 0 = sauber, 1 = Verstoß gefunden."""
    # Ausgabe robust gegen die Windows-Konsole (cp1252): UTF-8 erzwingen, sonst crasht
    # ein Zeichen wie „→" oder ein Umlaut mit UnicodeEncodeError (Linux/CI ist UTF-8).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = list(argv) if argv is not None else sys.argv[1:]
    verzeichnisse = args if args else list(SCAN_DIRS)

    gescannte, fehlend, ignoriert = _klassifiziere_ziele(verzeichnisse)

    # Fail-closed an der RICHTIGEN Invariante: nicht „existiert ein Pfad?", sondern
    # „wurde eine prüfbare .py-Datei gefunden?". Sonst gäbe ein leeres/falsches Ziel
    # (fehlend, leerer Ordner, Datei ohne .py) still grün, ohne etwas zu prüfen.
    if not gescannte:
        print(
            f"FEHLER: keine prüfbare .py-Datei in den Scan-Zielen gefunden "
            f"({', '.join(map(str, verzeichnisse))}) — Gate fail-closed."
        )
        return 1

    # Fehlende/ignorierte Ziele sichtbar machen (nicht still verschlucken) — Scan läuft weiter.
    if fehlend:
        print(f"WARNUNG: Scan-Ziel(e) nicht gefunden, übersprungen: {', '.join(fehlend)}")
    if ignoriert:
        print(f"WARNUNG: keine .py-Datei, übersprungen: {', '.join(ignoriert)}")

    verstoesse = pruefe_dateien(gescannte)

    # Verstöße zuerst behandeln und früh zurückkehren — sonst widerspräche der
    # Stub-HINWEIS unten einem Verstoß, der in genau diesen Dateien gefunden wurde.
    if verstoesse:
        _melde_verstoesse(verstoesse)
        return 1

    # Sauberer Lauf: sichtbar machen, wie viel tatsächlich geprüft wurde — ein Lauf
    # über reine __init__.py-Stubs (noch keine Bewertungslogik) ist "OK", prüft aber nichts.
    substanziell = [p for p in gescannte if p.name != "__init__.py"]
    if not substanziell:
        print(
            "HINWEIS: Keine Schwellen-Module mit Code gefunden (nur Stubs) — Guard ist als "
            "Enabler aktiv, prüft aktuell aber keinen Bewertungscode."
        )
    print(
        f"OK — keine hartcodierten Schwellen "
        f"({len(substanziell)} Modul-Datei(en) in: {', '.join(map(str, verzeichnisse))})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
