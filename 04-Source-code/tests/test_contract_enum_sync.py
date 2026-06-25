"""Contract-Guard: Enum-Wertemengen ueber alle Quellen synchron (Review-Finding #9, DTB-19).

Problem (PR #48): Die Enums sind an mehreren Stellen definiert und nur per Kommentar
synchron gehalten — eine OpenAPI-Spec kann nicht ueber getrennte Dateien `$ref`en, also
ist `SensorStatus` sogar dreifach kopiert:
  1. src/model/enums.py                     -> Quelle der Wahrheit (StrEnum)
  2. docs/api/v1/openapi.yaml               -> components.schemas.<Name>.enum
  3. docs/api/v1/g1-consumed.openapi.yaml   -> components.schemas.G1Current.properties.status.enum

Dieser Guard bricht, sobald eine Stelle driftet (z. B. Seam-Sync DTB-26 ergaenzt einen
Status wie `degraded` nur in einer Datei). So bleibt die ungesicherte Hand-Kopie
maschinell abgesichert, ohne Codegen einzufuehren.
"""

from pathlib import Path

import pytest
import yaml

from src.model import enums as enums_mod

_API_DIR = Path(__file__).resolve().parents[1] / "docs" / "api" / "v1"

# OpenAPI-Schema-Name (in openapi.yaml) -> gespiegelte StrEnum-Klasse in enums.py.
# AuditEventType taucht bewusst nicht in der API auf und wird daher nicht gespiegelt.
_MIRRORED_ENUMS = {
    "RiskLevel": enums_mod.RiskLevel,
    "SensorStatus": enums_mod.SensorStatus,
    "AlarmSeverity": enums_mod.AlarmSeverity,
    "AlarmState": enums_mod.AlarmState,
    "Source": enums_mod.Source,
}


def _load(filename: str) -> dict:
    with open(_API_DIR / filename, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _values(enum_cls) -> set[str]:
    return {member.value for member in enum_cls}


@pytest.mark.parametrize("schema_name,enum_cls", _MIRRORED_ENUMS.items())
def test_openapi_enum_spiegelt_enums_py(schema_name: str, enum_cls) -> None:
    """Jede Enum-Wertemenge in openapi.yaml ist identisch zur Quelle in enums.py."""
    yaml_values = set(_load("openapi.yaml")["components"]["schemas"][schema_name]["enum"])
    py_values = _values(enum_cls)
    assert yaml_values == py_values, (
        f"{schema_name}-Wertemenge driftet zwischen Spec und Modell:\n"
        f"  enums.py     : {sorted(py_values)}\n"
        f"  openapi.yaml : {sorted(yaml_values)}"
    )


def test_g1_consumed_status_gleich_sensorstatus() -> None:
    """Die dritte (hand-kopierte) Stelle: G1Current.status == SensorStatus."""
    g1 = _load("g1-consumed.openapi.yaml")
    g1_status = set(g1["components"]["schemas"]["G1Current"]["properties"]["status"]["enum"])
    py_values = _values(enums_mod.SensorStatus)
    assert g1_status == py_values, (
        "SensorStatus driftet in g1-consumed.openapi.yaml (G1Current.status):\n"
        f"  enums.py                : {sorted(py_values)}\n"
        f"  g1-consumed.openapi.yaml: {sorted(g1_status)}"
    )
