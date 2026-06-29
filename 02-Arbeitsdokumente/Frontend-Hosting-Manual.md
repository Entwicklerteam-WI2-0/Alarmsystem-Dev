# Frontend-Hosting-Manual (G3-SPA über das G2-Backend)

> **Zweck:** Wie das **G3-Frontend** (React/Vite-SPA) gebaut, über das **G2-Backend** ausgeliefert
> und auf dem **Raspberry Pi** betrieben wird. Aus **G2-Sicht (Hosting/Deploy)** — die *Bedienung* der
> Oberfläche und das UI-Konzept liegen in G3s eigener Doku (`frontendTESS26/Dokumente/10_UI-Konzept.md`).
>
> **Pflicht-Querverweise:** Pi-Deploy Schritt-für-Schritt → `Pi-Setup.md` §10 · allgemeines Pi-Hosting →
> `Raspberry-Pi-Hosting-Anleitung.md` · Mount-Code → `04-Source-code/src/main.py` (`_mount_frontend`).

---

## 1. Was ist das Frontend?

- **Gruppe 3 (Frontend & Integration)** liefert die Bedienoberfläche; Quelle: Repo/ZIP **`frontendTESS26`**, App-Root im Unterordner **`code/`**.
- **Stack:** React 19 · Vite 6 · TypeScript · Tailwind CSS · React-Router 7. Es ist eine **Single-Page-App (SPA)** — eine `index.html` + gebündelte Assets, **kein** laufender Node-Server im Betrieb.
- **Rolle in der Architektur:** reiner **Browser-Client**. G3 hostet selbst nichts (E-37); das Frontend **konsumiert** die G2-API (`/v1/...`) und den SSE-Alarmstream. G1/G3 reden nie direkt mit der DB (RB-01).

## 2. Hosting-Modell — Same-Origin über G2

Das gebaute Frontend wird **vom selben G2-FastAPI-Prozess** mit ausgeliefert:

| Pfad | Was |
|---|---|
| `GET /` , `/dashboard`, `/sensors`, … | Frontend (SPA) — gemountet aus dem gebauten `dist/` |
| `GET /v1/...` | G2-API (hat **Vorrang**, wird nie vom Frontend verschluckt) |

Weil UI **und** API auf derselben Origin (`http://<pi>:8000`) liegen, entfällt **CORS** komplett.
Aktiviert wird das über die Env-Variable **`G2_FRONTEND_DIR`** (Pfad zum `dist/`). Ist sie **nicht** gesetzt,
läuft G2 als reine API (kein Mount). Implementierung: `_mount_frontend` / `_SPAStaticFiles` in `src/main.py`.

> **SPA-Fallback:** Direktaufruf/Reload einer Unterseite (z. B. `/dashboard`) liefert serverseitig
> `index.html` zurück; das clientseitige Routing übernimmt React-Router. `/v1/*` ist davon ausgenommen —
> ein API-404 bleibt ein API-404 (Contract-Fehlerformat), keine HTML-Seite.

## 3. Voraussetzungen (nur zum Bauen)

- **Node.js ≥ 20** + npm (Vite 6 / React 19). Wird **nur zum Bauen** gebraucht — auf dem Pi selbst ist **kein** Node nötig, dort läuft nur Python/uvicorn + die statischen Dateien.
- Empfehlung: **lokal auf einem Dev-Rechner bauen**, nur das fertige `dist/` auf den Pi kopieren (schneller als ein Build auf dem ARM-Pi).

## 4. Konfiguration (Vite-Env, `VITE_*`)

Build-Zeit-Variablen (werden beim `vite build` fest in das Bundle gebacken):

| Variable | Default | Bedeutung |
|---|---|---|
| `VITE_API_MODE` | `mock` | `live` = echte G2-API (HTTP/SSE) · `mock` = eingebaute Demo-Daten. **Für echten Betrieb `live`!** |
| `VITE_API_BASE` | `/v1` | API-Basis-Pfad. Bei Same-Origin-Hosting **leer lassen** (relativ `/v1`). |
| `VITE_API_TOKEN` | — | Bearer-Token für **schreibende** Endpoints (`POST /v1/thresholds`). Für die reine Anzeige (GET + SSE) **nicht** nötig. Muss zum G2 `G2_API_KEY` passen. |
| `VITE_MOCK_SCENARIO` | `normal` | Nur im Mock-Modus: Demo-Szenario. |

> ⚠️ **Häufigster Fehler:** `.env.development` steht ab Werk auf `VITE_API_MODE=mock`. Wird ohne
> `VITE_API_MODE=live` gebaut, zeigt die UI **Demo-Daten statt echter Werte** — sieht echt aus, ist es
> nicht. Für den Produktions-Build immer eine `.env.production` mit `VITE_API_MODE=live` anlegen.

## 5. Bauen

Im Frontend-Ordner **`code/`**:

```bash
echo "VITE_API_MODE=live" > .env.production    # Live-Modus erzwingen (siehe Warnung oben)
npm ci                                          # exakte Abhängigkeiten aus package-lock.json
npm run build                                   # tsc -b && vite build  ->  erzeugt code/dist/
```

Ergebnis: `code/dist/` mit `index.html` + `assets/` (gebündeltes JS/CSS). Größenordnung ~110 kB gzip — Pi-tauglich.

## 6. Auf den Pi deployen

Kurzform (vollständig in **`Pi-Setup.md` §10**):

```bash
# 1) dist/ auf den Pi kopieren (NICHT ins Git committen -- Build-Artefakt):
rsync -av code/dist/ pi@icedetection.local:/home/pi/frontend_dist/

# 2) auf dem Pi in der .env den Pfad setzen:
#    G2_FRONTEND_DIR=/home/pi/frontend_dist

# 3) uvicorn neu starten (bzw. systemd-Service neu laden)
```

Aktivierungs-Schalter ist in `04-Source-code/.env.example` dokumentiert.

## 7. Lokaler Entwicklungs-Modus (optional, ohne G2-Mount)

Für die G3-Entwicklung läuft der **Vite-Dev-Server** eigenständig und proxyt API-Calls ans Backend:

```bash
cd code && npm run dev        # http://localhost:5173
```

`vite.config.ts` proxyt `/v1` → `http://localhost:8000` (lokales G2). Das betrifft **nur** den Dev-Server;
der Produktions-Build (Same-Origin über G2) braucht keinen Proxy.

## 8. UI-Überblick (Seiten & Rollen)

Die Oberfläche bietet sieben Seiten; sichtbar je nach gewähltem **Profil** (Rollen-Filterung):

| Profil | Sichtbare Seiten (Kurz) |
|---|---|
| **IT** | Sensoren · Historie · Einstellungen |
| **Management** | Dashboard · Historie |
| **Winterdienst** | Dashboard · Sensoren · Historie |
| **Fluglotsen** | Dashboard · Historie |
| **Controlling** | Dashboard · Historie |
| **Luftfahrtbehörde** | Historie · Einstellungen |
| **Entwicklungsteam** | alle |
| **Sicherheitsabteilung** | Dashboard · Historie · Einstellungen |

Seiten: `/dashboard` (Lage/Ampel) · `/sensors` (Sensorstatus) · `/history` (Messwert-/Alarm-Historie) ·
`/alarms` (Alarme/Quittierung) · `/runways` (Bahnstatus) · `/settings` (Schwellen/Config) · `/start` (Profilwahl).

> 🔒 **Sicherheits-Klarstellung (wichtig):** Die Profil-/Rollenwahl ist **reine UI-Personalisierung**
> (im Browser via `localStorage` gespeichert) — **keine** Zugriffskontrolle. Sie verhindert serverseitig
> nichts. Die **echten** Grenzen liegen im Backend: **RB-01** (kein Aktor — das System gibt keine Startbahn
> frei/sperrt nicht; Alarm-Quittierung ist reine UI-/Audit-Aktion) und der **API-Key-Schreibschutz**
> (`G2_API_KEY`, nur für `POST`-Endpoints). Wer echte Autorisierung braucht, muss sie in G2 ergänzen (NF-07/AE-02).

## 9. Verifikation nach dem Deploy

```bash
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/            # -> index.html  [200]
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/dashboard   # -> index.html  [200]  (SPA-Fallback)
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/v1/health   # -> {"status":"ok"} [200] (API-Vorrang)
```

Im Browser `http://<pi-ip>:8000/` öffnen → Profil wählen → echte Werte (nicht Mock) müssen erscheinen.

## 10. Update einer neuen Frontend-Version

1. Neue G3-Version holen (Git-Pull/neues ZIP) → `code/`.
2. Schritt 5 (Bauen) + Schritt 6 (Deployen) erneut ausführen.
3. Browser-Hard-Reload (Vite vergibt gehashte Asset-Namen → kein Stale-Cache, aber `index.html` ggf. neu laden).

## 11. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| UI zeigt **Demo-/Mock-Werte** statt echter Daten | Ohne `VITE_API_MODE=live` gebaut → Schritt 5 mit `.env.production` neu bauen. |
| **Weiße Seite**, Assets laden nicht (404 auf `/assets/...`) | Falscher Build-`base` oder unvollständig kopiertes `dist/`. Mount erfolgt am Root `/` → Vite-`base` muss `/` sein (Default). `dist/` vollständig kopieren. |
| **404 beim Reload** auf `/dashboard` o. ä. | SPA-Fallback greift nicht → prüfen, dass `G2_FRONTEND_DIR` gesetzt ist und auf das `dist/` zeigt (`_mount_frontend`-Logzeile beim Start). |
| **CORS-Fehler** im Browser | Tritt bei Same-Origin-Hosting **nicht** auf. Erscheint er, läuft das Frontend doch auf anderer Origin (z. B. Vite-Dev-Server) → dann G2 `G2_CORS_ORIGINS` setzen. |
| API-Calls schlagen mit **401/503** auf `POST` fehl | Schreibschutz: `VITE_API_TOKEN` (Frontend) muss zum `G2_API_KEY` (Backend) passen; GET/SSE sind ungeschützt. |
| Frontend lädt, aber **kein Mount** im G2-Log | `G2_FRONTEND_DIR` nicht gesetzt oder kein Verzeichnis → reiner API-Betrieb. `.env` prüfen + uvicorn neu starten. |

---

## Referenzen

- **Mount-Code:** `04-Source-code/src/main.py` → `_mount_frontend`, `_SPAStaticFiles` (+ Test `tests/test_frontend_hosting.py`)
- **Aktivierung:** `04-Source-code/.env.example` → `G2_FRONTEND_DIR`
- **Pi-Deploy:** `Pi-Setup.md` §10 · **Pi allgemein:** `Raspberry-Pi-Hosting-Anleitung.md`
- **API-Vertrag (was das Frontend konsumiert):** `04-Source-code/docs/API_FROZEN_v1.md` + `docs/api/v1/openapi.yaml`
- **G3-UI-Konzept (Bedienung):** `frontendTESS26/Dokumente/10_UI-Konzept.md` (G3-Repo)
