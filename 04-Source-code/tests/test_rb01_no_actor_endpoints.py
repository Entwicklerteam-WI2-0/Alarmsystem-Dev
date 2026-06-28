"""Tests fuer den RB-01-Guard gegen Aktor-Endpoints (P4.5 / DTB-42)."""

from tools.check_rb01_no_actor_endpoints import (
    finde_verstoesse_in_openapi_text,
    finde_verstoesse_in_python_text,
    main,
)


def test_python_route_mit_unlock_wird_blockiert():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post("/runway/unlock")
def route():
    return {"ok": True}
"""

    verstoesse = finde_verstoesse_in_python_text(code, "src/api/v1.py")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "unlock"
    assert verstoesse[0].endpoint == "/runway/unlock"


def test_async_python_route_mit_execute_wird_blockiert():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post("/runway/execute")
async def route():
    return {"ok": True}
"""

    verstoesse = finde_verstoesse_in_python_text(code, "src/api/v1.py")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "execute"
    assert verstoesse[0].endpoint == "/runway/execute"


def test_python_route_path_keyword_argument_wird_blockiert():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post(path="/runway/unlock")
def route():
    return {"ok": True}
"""

    verstoesse = finde_verstoesse_in_python_text(code, "src/api/v1.py")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "unlock"
    assert verstoesse[0].endpoint == "/runway/unlock"


def test_python_route_mit_freigabe_wird_blockiert():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post("/runway/freigabe")
def route():
    return {"ok": True}
"""

    verstoesse = finde_verstoesse_in_python_text(code, "src/api/v1.py")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "freigabe"
    assert verstoesse[0].endpoint == "/runway/freigabe"


def test_python_route_mit_sperr_wird_blockiert():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post("/runway/sperren")
def route():
    return {"ok": True}
"""

    verstoesse = finde_verstoesse_in_python_text(code, "src/api/v1.py")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "sperr"
    assert verstoesse[0].endpoint == "/runway/sperren"


def test_python_syntaxfehler_ist_fail_closed():
    verstoesse = finde_verstoesse_in_python_text(
        "@router.post('/v1/health')\ndef kaputt(:\n",
        "src/api/v1.py",
    )

    assert len(verstoesse) == 1
    assert verstoesse[0].fail_closed is True
    assert "parsebar" in verstoesse[0].grund


def test_python_route_docstring_mit_freigabe_ist_sauber():
    code = '''
from fastapi import APIRouter

router = APIRouter()

@router.get("/v1/assessment/current")
def route():
    """RB-01: keine automatische Freigabe."""
    return {"ok": True}
'''

    assert finde_verstoesse_in_python_text(code, "src/api/v1.py") == []


def test_ack_route_bleibt_erlaubt_weil_keine_bahn_steuerung():
    code = """
from fastapi import APIRouter

router = APIRouter()

@router.post("/alarms/{id}/ack")
def route():
    return {"ok": True}
"""

    assert finde_verstoesse_in_python_text(code, "src/api/v1.py") == []


def test_openapi_path_mit_sperr_wird_blockiert():
    yaml_text = """
paths:
  /v1/runway/sperren:
    post:
      summary: Verbotener Aktor
"""

    verstoesse = finde_verstoesse_in_openapi_text(yaml_text, "docs/api/v1/openapi.yaml")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "sperr"
    assert verstoesse[0].endpoint == "/v1/runway/sperren"


def test_openapi_path_mit_vier_spaces_wird_blockiert():
    yaml_text = """
paths:
    /v1/runway/execute:
      post:
        summary: Verbotener Aktor
"""

    verstoesse = finde_verstoesse_in_openapi_text(yaml_text, "docs/api/v1/openapi.yaml")

    assert len(verstoesse) == 1
    assert verstoesse[0].keyword == "execute"
    assert verstoesse[0].endpoint == "/v1/runway/execute"


def test_openapi_beschreibung_mit_execute_beispiel_ist_sauber():
    yaml_text = """
info:
  title: G2 API
  description: |
    Verbotene Muster:
      /v1/runway/execute:
        wird durch RB-01 blockiert
paths:
  /v1/health:
    get:
      summary: Health
"""

    assert finde_verstoesse_in_openapi_text(yaml_text, "docs/api/v1/openapi.yaml") == []


def test_openapi_erlaubte_endpoint_liste_ist_sauber():
    yaml_text = """
paths:
  /v1/health:
    get:
      summary: Health
  /v1/assessment/current:
    get:
      summary: Bewertung
  /v1/thresholds:
    get:
      summary: Schwellen lesen
    post:
      summary: Schwellen versioniert anlegen
  /v1/readings:
    get:
      summary: Historie
  /v1/alarms:
    get:
      summary: Alarme
  /v1/alarms/stream:
    get:
      summary: Stream
  /v1/alarms/{id}/ack:
    post:
      summary: Quittierung
"""

    assert finde_verstoesse_in_openapi_text(yaml_text, "docs/api/v1/openapi.yaml") == []


def test_main_schreibt_verstoesse_auf_stderr(tmp_path, capsys):
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(
        """
paths:
    /v1/runway/execute:
      post:
        summary: Verbotener Aktor
""",
        encoding="utf-8",
    )

    code = main([str(openapi)])
    captured = capsys.readouterr()

    assert code == 1
    assert "FEHLER" in captured.err
    assert "/v1/runway/execute" in captured.err
    assert captured.out == ""


def test_main_fehler_wenn_ziel_nicht_existiert(tmp_path, capsys):
    code = main([str(tmp_path / "nicht_vorhanden.yaml")])
    captured = capsys.readouterr()

    assert code == 1
    assert "Scan-Fehler" in captured.err
    assert "verbotene Aktor-Endpoints" not in captured.err
    assert "fail-closed" in captured.err
    assert captured.out == ""
