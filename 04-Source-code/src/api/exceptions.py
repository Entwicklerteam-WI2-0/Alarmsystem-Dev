"""Geteilte API-Exceptions der /v1/-Naht.

Eigene Modul-Heimat, damit der Exception-Handler (main.py) und die werfende Stelle
(`get_runtime` in runtime.py) dieselbe Exception teilen, ohne dass eine Schicht aus
einer anderen importieren muss (Review-Finding: keine Layer-ueberkreuzende
Exception-Definition). Der zugehoerige Handler in main.py bildet sie contract-konform
auf 503 `Error {code, message}` ab (NF-01: nie GRUEN, auch nicht bei Startup-Fehlern).
"""


class ContractError(RuntimeError):
    """Basisklasse fuer API-Fehler, die contract-konform als `{code, message}`
    gemeldet werden. Traegt HTTP-Status, maschinenlesbaren Code und Meldung.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class RuntimeNotReadyError(ContractError):
    """`app.state.runtime` fehlt — lifespan hat den DI-Graph (noch) nicht gesetzt.

    Eigene Exception statt rohem AttributeError: faengt `build_runtime()` im lifespan
    vor dem yield eine unbehandelte Exception (oder ist `runtime` aus anderem Grund
    nicht gesetzt), wuerde ein direkter `app.state.runtime`-Zugriff als FastAPI-
    Standard-500 mit `{detail}` durchschlagen und den Fehler-Contract brechen. Der
    registrierte Exception-Handler bildet diese Exception contract-konform auf
    503 `{code, message}` ab (NF-01: nie GRUEN, auch nicht bei Startup-Fehlern).
    """

    def __init__(self, message: str) -> None:
        super().__init__(503, "SERVICE_UNAVAILABLE", message)


class APIKeyMissingError(ContractError):
    """Serverseitiger API-Key nicht konfiguriert — Schreibzugriff fail-safe gesperrt."""

    def __init__(self, message: str) -> None:
        super().__init__(503, "SERVICE_UNAVAILABLE", message)


class AuthenticationError(ContractError):
    """Fehlender oder ungueltiger API-Key fuer einen geschuetzten Endpoint."""

    def __init__(self, message: str) -> None:
        super().__init__(401, "UNAUTHORIZED", message)
