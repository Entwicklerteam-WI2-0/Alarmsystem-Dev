# erinnerung/ — Geteiltes Projektgedächtnis

Diese Dateien sind das **gemeinsame Gedächtnis** des Teams. Der `/start`-Befehl liest sie beim
Sitzungsbeginn, damit jede:r mit demselben aktuellen Stand startet — auch nach Tages-/Personenwechsel.

**Pflege:** primär **Lucas**. Kurz, faktisch, Deutsch. Lieber knappe, aktuelle Notizen als lange, veraltete.

| Datei | Inhalt |
|---|---|
| `stand.md` | **Aktueller Stand**: woran wird gearbeitet, was ist als Nächstes dran, Blocker |
| *(optional)* `entscheidungen.md` | Kurz-Spiegel wichtiger Entscheidungen (Detail: `02-Arbeitsdokumente/Entscheidungslog-…`) |
| *(optional)* `offene-fragen.md` | Offene Punkte, die noch jemand klären muss |

> Diese Dateien **committen** (sie sind geteilt). Keine Secrets, keine personenbezogenen Bewertungen.

## Pflege-Regel: per Hand, append-only — fremde Einträge nie überschreiben

Diese Dateien werden **von Hand** gepflegt (kein automatisches Überschreiben). Beim Bearbeiten gilt:

- **Eigene Beiträge immer an der passenden Stelle anhängen**; **Einträge anderer Personen niemals
  überschreiben, ersetzen oder löschen** — gilt für **alle** Dateien hier. So bleiben parallele Beiträge
  mehrerer Leute konfliktarm.
- **Das Journal (`journal/<datum>.md`) ist strikt append-only** — nur unten einen neuen Block anhängen,
  bestehende Blöcke nie ändern (je Person/Session ein eigener Block; hält Merges konfliktfrei).
- Beim Verdichten von `stand.md` nur **eigene/veraltete** Notizen ersetzen — **fremde, frische Beiträge
  stehen lassen**.
- Alle Mitglieder (und ihre Agenten) dürfen `erinnerung/` bearbeiten; Pflege primär bei Lucas. Committen
  (geteilt), keine Secrets.
