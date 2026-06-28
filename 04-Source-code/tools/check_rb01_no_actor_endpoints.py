"""P4.5 / DTB-42: RB-01-Guard gegen Aktor-Endpoints.

RB-01 verbietet jeden API-Pfad, der die Startbahn automatisch freigibt, sperrt
oder sonst steuert. Dieser Guard prueft deshalb echte FastAPI-Routen und OpenAPI-
Path-Keys auf die vereinbarten Aktor-Keywords:

    unlock, freigabe, sperr, execute

Bewusst werden Kommentare, Docstrings und OpenAPI-Beschreibungen nicht durchsucht:
README/Code duerfen RB-01 erklaeren, ohne den Guard rot zu faerben. Entscheidend
ist, dass kein Endpoint-Pfad ein Aktor-Vokabular traegt.

Der OpenAPI-Scan ist absichtlich ein kleiner struktureller Textscan statt ein
YAML-Parser: Geprueft werden nur Path-Keys innerhalb des top-level `paths:`-
Abschnitts. Beschreibungen, Beispiele und Kommentare ausserhalb davon duerfen
verbotene Muster als Dokumentation nennen.

Bekannte Grenzen (bewusst) - zwei Instanzen, die zweite faengt die erste ab:
(a) Routing-Form: Der Python-Scan liest nur Decorator-Routen
    (`@app.get("/runway/unlock")`, `@router.api_route(path=...)`). Programmatische
    Registrierung ausserhalb eines Decorators wird NICHT erkannt - etwa
    `app.add_api_route("/runway/unlock", handler)` oder
    `router.include_router(actor_router, prefix="/v1/runway/execute")`. Auffangnetz:
    Jeder reale Endpoint MUSS im eingefrorenen Contract `docs/api/v1/openapi.yaml`
    stehen, wo der OpenAPI-Path-Key-Scan unabhaengig von der Python-Form greift.
    Bleibt ein Pfad in beiden aussen vor (programmatisch registriert UND nicht in der
    Spec), faengt ihn das Code-Review (zweite Instanz).
(b) Keyword-Liste: VERBOTENE_AKTOR_KEYWORDS ist bewusst klein und kuratiert und deckt
    Synonyme wie `approve`, `enable`, `open`, `activate` oder `close` NICHT ab (anders
    als beim Schwellen-Guard gibt es hier keinen `# noqa`-Mechanismus). Neue
    Aktor-Vokabeln werden bei Bedarf ergaenzt; bis dahin bleibt auch das eine
    Code-Review-Aufgabe.

Aufruf aus `04-Source-code/`:
    python tools/check_rb01_no_actor_endpoints.py

Exit-Code 0 = sauber, 1 = Aktor-Endpoint oder nicht pruefbares Ziel gefunden.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# `execute` ist bewusst breit: In RB-01-Naehe darf kein API-Pfad einen automatisch
# ausgefuehrten Bahn-/Runway-Befehl nahelegen. Legitime technische Execute-Pfade
# gehoeren nicht in die oeffentliche G2-/v1-API.
VERBOTENE_AKTOR_KEYWORDS: tuple[str, ...] = ("unlock", "freigabe", "sperr", "execute")

FASTAPI_METHODEN: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}
)

_BASIS = Path(__file__).resolve().parent.parent
DEFAULT_ZIELE: tuple[Path, ...] = (
    _BASIS / "src",
    _BASIS / "docs" / "api" / "v1" / "openapi.yaml",
)

_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+:\s*(?:#.*)?$")
_OPENAPI_PATH_RE = re.compile(r"^\s+(/[^:]*):\s*(?:#.*)?$")


@dataclass(frozen=True)
class Verstoss:
    """Ein verbotener Aktor-Endpoint oder ein fail-closed-Fund."""

    datei: str
    zeile: int
    endpoint: str
    keyword: str
    grund: str
    fail_closed: bool = False


def _keyword(endpoint: str) -> str | None:
    endpoint_normalisiert = endpoint.casefold()
    for keyword in VERBOTENE_AKTOR_KEYWORDS:
        if keyword in endpoint_normalisiert:
            return keyword
    return None


def _string_literal(knoten: ast.AST) -> str | None:
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
        return knoten.value
    return None


def _decorator_endpoint(decorator: ast.AST) -> tuple[str, int] | None:
    """Extrahiert den Endpoint-Pfad aus FastAPI-Decoratoren.

    Erkannt werden Formen wie `@app.get("/v1/health")`,
    `@router.post(path="/alarms/{id}/ack")` und `@router.api_route(...)`.
    """
    if not isinstance(decorator, ast.Call):
        return None
    fn = decorator.func
    if not (isinstance(fn, ast.Attribute) and fn.attr in FASTAPI_METHODEN):
        return None

    endpoint = _string_literal(decorator.args[0]) if decorator.args else None
    if endpoint is None:
        for keyword in decorator.keywords:
            if keyword.arg == "path":
                endpoint = _string_literal(keyword.value)
                break
    if endpoint is None:
        return None
    return endpoint, decorator.lineno


def _fail_closed(datei: str, zeile: int, grund: str) -> Verstoss:
    return Verstoss(
        datei=datei,
        zeile=zeile,
        endpoint="<nicht pruefbar>",
        keyword="<fail-closed>",
        grund=grund,
        fail_closed=True,
    )


def finde_verstoesse_in_python_text(quelltext: str, dateiname: str) -> list[Verstoss]:
    """Findet verbotene Aktor-Keywords in FastAPI-Route-Decoratoren."""
    try:
        baum = ast.parse(quelltext)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        zeile = getattr(exc, "lineno", None) or 1
        return [
            _fail_closed(
                dateiname,
                zeile,
                f"Python-Datei nicht parsebar: {exc.__class__.__name__}",
            )
        ]

    verstoesse: list[Verstoss] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in knoten.decorator_list:
            endpoint_info = _decorator_endpoint(decorator)
            if endpoint_info is None:
                continue
            endpoint, zeile = endpoint_info
            keyword = _keyword(endpoint)
            if keyword is None:
                continue
            verstoesse.append(
                Verstoss(
                    datei=dateiname,
                    zeile=zeile,
                    endpoint=endpoint,
                    keyword=keyword,
                    grund="RB-01: verbotener Aktor-Endpoint im FastAPI-Pfad",
                )
            )
    return verstoesse


def finde_verstoesse_in_openapi_text(quelltext: str, dateiname: str) -> list[Verstoss]:
    """Findet verbotene Aktor-Keywords in OpenAPI-Path-Keys."""
    verstoesse: list[Verstoss] = []
    in_paths = False
    for zeile, inhalt in enumerate(quelltext.splitlines(), start=1):
        if inhalt.startswith("paths:"):
            in_paths = True
            continue
        if in_paths and _TOP_LEVEL_KEY_RE.match(inhalt):
            in_paths = False
        if not in_paths:
            continue
        match = _OPENAPI_PATH_RE.match(inhalt)
        if match is None:
            continue
        endpoint = match.group(1)
        keyword = _keyword(endpoint)
        if keyword is None:
            continue
        verstoesse.append(
            Verstoss(
                datei=dateiname,
                zeile=zeile,
                endpoint=endpoint,
                keyword=keyword,
                grund="RB-01: verbotener Aktor-Endpoint im OpenAPI-Pfad",
            )
        )
    return verstoesse


def _dateien_aus_zielen(ziele: Iterable[Path]) -> tuple[list[Path], list[Verstoss]]:
    dateien: list[Path] = []
    verstoesse: list[Verstoss] = []

    for ziel in ziele:
        if ziel.is_dir():
            dateien.extend(sorted(ziel.rglob("*.py")))
            continue
        if ziel.is_file():
            if ziel.suffix in {".py", ".yaml", ".yml"}:
                dateien.append(ziel)
            continue
        verstoesse.append(_fail_closed(str(ziel), 1, "Scan-Ziel nicht gefunden"))

    eindeutig: dict[Path, Path] = {}
    for datei in dateien:
        eindeutig.setdefault(datei.resolve(), datei)
    return list(eindeutig.values()), verstoesse


def pruefe_dateien(dateien: Iterable[Path]) -> list[Verstoss]:
    verstoesse: list[Verstoss] = []
    for datei in dateien:
        try:
            text = datei.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            verstoesse.append(
                _fail_closed(str(datei), 1, f"Datei nicht lesbar: {exc.__class__.__name__}")
            )
            continue

        if datei.suffix == ".py":
            verstoesse.extend(finde_verstoesse_in_python_text(text, str(datei)))
        elif datei.suffix in {".yaml", ".yml"}:
            verstoesse.extend(finde_verstoesse_in_openapi_text(text, str(datei)))
    return verstoesse


def pruefe_ziele(ziele: Iterable[str | Path]) -> list[Verstoss]:
    pfade = [Path(ziel) for ziel in ziele]
    dateien, verstoesse = _dateien_aus_zielen(pfade)
    if not dateien:
        return [
            *verstoesse,
            _fail_closed(
                ", ".join(str(ziel) for ziel in pfade) or "<keine Ziele>",
                1,
                "keine pruefbare Python-/OpenAPI-Datei gefunden",
            ),
        ]
    return [*verstoesse, *pruefe_dateien(dateien)]


def _melde_verstoesse(verstoesse: list[Verstoss]) -> None:
    if all(verstoss.fail_closed for verstoss in verstoesse):
        print(
            "Scan-Fehler: RB-01-Guard konnte Scan-Ziele nicht pruefen (fail-closed):\n",
            file=sys.stderr,
        )
    else:
        # Gemischte Liste (echte Funde + fail-closed): den Scan-Fehler-Anteil im Banner
        # nennen, damit er nicht als bloss eine weitere Endpoint-Zeile untergeht.
        zusatz = " (inkl. Scan-Fehler)" if any(v.fail_closed for v in verstoesse) else ""
        print(
            f"FEHLER: RB-01-Guard hat verbotene Aktor-Endpoints gefunden{zusatz}:\n",
            file=sys.stderr,
        )
    for verstoss in verstoesse:
        print(
            f"  {verstoss.datei}:{verstoss.zeile}: {verstoss.endpoint} "
            f"({verstoss.keyword}) — {verstoss.grund}",
            file=sys.stderr,
        )
    print(
        "\nRB-01 verlangt reine Entscheidungsunterstuetzung: kein Freigabe-, "
        "Sperr-, Unlock- oder Execute-Endpoint.",
        file=sys.stderr,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    ziele = args if args else DEFAULT_ZIELE
    verstoesse = pruefe_ziele(ziele)
    if verstoesse:
        _melde_verstoesse(verstoesse)
        return 1
    print(f"OK — RB-01: keine Aktor-Endpoints gefunden ({', '.join(str(ziel) for ziel in ziele)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
