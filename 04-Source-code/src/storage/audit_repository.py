"""Append-only Audit-Log-Repository (DTB-29 / NF-09).

Das Audit-Log ist das "Tagebuch" des Systems: jedes relevante Ereignis wird als
Zeile angehaengt und bleibt unveraenderlich. Die Schnittstelle bietet darum
bewusst NUR `append` -- kein update, kein delete (append-only per Design).

Zweite Absicherung folgt auf DB-Ebene (Trigger + eingeschraenkte Grants, Variante C);
die konkrete MySQL-Implementierung (rohes PyMySQL, parametrisierte Queries) kommt mit
DTB-28/DTB-55. Diese Datei haelt die DB-agnostische Naht + ein In-Memory-Double.
"""

from abc import ABC, abstractmethod

from src.model.schemas import AuditLogEntry


class AuditRepository(ABC):
    """Abstrakte append-only Persistenz fuer Audit-Log-Eintraege.

    Bewusst minimal: nur `append`. Es gibt keine Methode zum Aendern oder Loeschen,
    damit das Tagebuch-Prinzip (NF-09) schon durch die Schnittstelle erzwungen wird.
    """

    @abstractmethod
    def append(self, entry: AuditLogEntry) -> int:
        """Haengt einen Eintrag an und gibt die vergebene ID zurueck.

        Args:
            entry: Der unveraenderliche Tagebuch-Eintrag (AuditLogEntry).

        Returns:
            Die vom Speichermedium vergebene ID (z. B. AUTO_INCREMENT).
        """
        ...


class InMemoryAuditRepository(AuditRepository):
    """In-Memory-Double fuer Tests und lokale Laeufe (keine DB noetig).

    Vergibt fortlaufende IDs ab 1 und haelt die Eintraege in Einfuege-Reihenfolge.
    Spiegelt das append-only-Verhalten der spaeteren MySQL-Implementierung.
    """

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def append(self, entry: AuditLogEntry) -> int:
        new_id = len(self._entries) + 1
        # Eintrag mit vergebener ID ablegen; das Original bleibt unangetastet.
        self._entries.append(entry.model_copy(update={"id": new_id}))
        return new_id

    def all(self) -> list[AuditLogEntry]:
        """Liest alle Eintraege in Einfuege-Reihenfolge (nur lesen)."""
        return list(self._entries)
