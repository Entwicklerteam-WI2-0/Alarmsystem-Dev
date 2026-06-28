"""Tests fuer den API-Key-Guard `require_api_key` (DTB-63, NF-07).

Prueft: fail-safe-closed bei nicht gesetztem `G2_API_KEY` (503), 401 bei
fehlendem/falschem Schluessel, Durchlass bei korrektem Schluessel — und als
Regression (Bug aus #116): ein Nicht-ASCII-Token loest sauber 401 aus statt
eines unauthentifiziert ausloesbaren `TypeError`/500.
"""

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.api.exceptions import ApiKeyNotConfiguredError, AuthenticationError
from src.api.security import API_KEY_ENV, require_api_key

_KEY = "geheim-test-key-123"


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_key_not_configured_raises_503_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: G2_API_KEY nicht gesetzt -> Schreibzugriff generell ablehnen.
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    # Act/Assert: fail-safe-closed (lieber kein Schreibzugriff als ein unbewachter).
    with pytest.raises(ApiKeyNotConfiguredError):
        require_api_key(_creds(_KEY))


def test_empty_env_key_treated_as_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    # Leerer Key = nicht konfiguriert (nicht "leerer gueltiger Key").
    monkeypatch.setenv(API_KEY_ENV, "")
    with pytest.raises(ApiKeyNotConfiguredError):
        require_api_key(_creds(_KEY))


def test_valid_key_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    # Kein Fehler -> Guard laesst durch (Rueckgabe None).
    assert require_api_key(_creds(_KEY)) is None


def test_wrong_key_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    with pytest.raises(AuthenticationError):
        require_api_key(_creds("falscher-key"))


def test_missing_credentials_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    # Kein Authorization-Header -> credentials ist None -> 401 (nicht 503).
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    with pytest.raises(AuthenticationError):
        require_api_key(None)


def test_non_ascii_token_raises_401_not_typeerror(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression (#116): ein Nicht-ASCII-Token (z. B. 'ue' als U+00FC) darf KEINEN
    # TypeError aus secrets.compare_digest(str) und damit keinen 500 ausloesen,
    # sondern muss als regulaerer Fehlversuch in 401 muenden.
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    with pytest.raises(AuthenticationError):
        require_api_key(_creds("schl\xfcssel-mit-umlaut"))
