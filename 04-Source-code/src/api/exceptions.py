"""Geteilte API-Exceptions der /v1/-Naht.

Eigene Modul-Heimat, damit der Exception-Handler (main.py) und die werfende Stelle
(`get_runtime` in runtime.py) dieselbe Exception teilen, ohne dass eine Schicht aus
einer anderen importieren muss (Review-Finding: keine Layer-ueberkreuzende
Exception-Definition). Der zugehoerige Handler in main.py bildet sie contract-konform
auf 503 `Error {code, message}` ab (NF-01: nie GRUEN, auch nicht bei Startup-Fehlern).
"""


class RuntimeNotReadyError(RuntimeError):
    """`app.state.runtime` fehlt — lifespan hat den DI-Graph (noch) nicht gesetzt.

    Eigene Exception statt rohem AttributeError: faengt `build_runtime()` im lifespan
    vor dem yield eine unbehandelte Exception (oder ist `runtime` aus anderem Grund
    nicht gesetzt), wuerde ein direkter `app.state.runtime`-Zugriff als FastAPI-
    Standard-500 mit `{detail}` durchschlagen und den Fehler-Contract brechen. Der
    registrierte Exception-Handler bildet diese Exception contract-konform auf
    503 `{code, message}` ab (NF-01: nie GRUEN, auch nicht bei Startup-Fehlern).
    """


class AuthenticationError(RuntimeError):
    """Schreibzugriff mit fehlendem oder ungueltigem API-Key (DTB-63, NF-07).

    Der registrierte Handler in main.py bildet sie contract-konform auf 401
    `Error {code, message}` ab (nie rohes 403/`{detail}` der FastAPI-Security).
    """


class ApiKeyNotConfiguredError(RuntimeError):
    """`G2_API_KEY` ist nicht gesetzt -> Schreibzugriff generell abgelehnt (503).

    Fail-safe-closed (NF-01-Geist): lieber kein Schreibzugriff als ein unbewachter.
    Der Handler in main.py bildet sie auf 503 `Error {code, message}` ab.
    """
