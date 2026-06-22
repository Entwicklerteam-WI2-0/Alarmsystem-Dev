# Pi-Setup — Datenbank-Zugang (G2 Vereisungserkennung)

> Ergänzt `Raspberry-Pi-Hosting-Anleitung.md` um den **DB-Zugang**.
> Verifiziert am 2026-06-22 · MariaDB 11.8.6 · Debian 13 (trixie).

## Eckdaten

| | Wert |
|---|---|
| Hostname | `icedetection.local` |
| IP (falls `.local` nicht geht) | `192.168.1.102` |
| Pi-Benutzer (SSH) | `pi` |
| Datenbank | `vereisung` |
| DB-Benutzer (App) | `anr_app` (darf nur `vereisung`) |
| DB-Passwort | im **Team-Passwort-Manager** — NIE ins Git |
| ENV-Vorlage | `04-Source-code/source/.env.example` |

> Voraussetzung: Laptop und Pi im **selben Netz** (LAN/WLAN).

---

## 1. Auf den Pi verbinden (SSH)

```bash
ssh pi@icedetection.local      # oder: ssh pi@192.168.1.102
```
**VS Code:** Extension „Remote - SSH" → `Cmd+Shift+P` → „Remote-SSH: Connect to Host" → `ssh pi@icedetection.local`.

**Ohne Passwort (einmalig, am Laptop):**
```bash
ssh-keygen -t ed25519
ssh-copy-id pi@icedetection.local
```

---

## 2. Auf die Datenbank zugreifen

### A — direkt auf dem Pi
```bash
mariadb -u anr_app -p          # App-Passwort
```
```sql
USE vereisung;
SHOW TABLES;
```

### B — grafisch vom Laptop (DBeaver, empfohlen)
DBeaver tunnelt **durch SSH** → DB bleibt sicher auf dem Pi.
- **Main:** Host `127.0.0.1` · Port `3306` · DB `vereisung` · User `anr_app` + Passwort
- **SSH:** „Use SSH Tunnel" ✅ · Host `icedetection.local` · User `pi`

> **Merksatz: DB zu, API offen.** MariaDB lauscht nur auf `127.0.0.1` (kein `0.0.0.0`).
> Team kommt über **SSH** an die DB. G1/G3 reden mit der **API**, nie direkt mit der DB (RB-01, §7).

---

## 3. Sicherheits-Regeln (kurz)

- **DB nur lokal** (`127.0.0.1`) — nicht öffnen. (NF-07)
- **Passwort nie committen.** Echte Werte in `04-Source-code/source/.env` (gitignored, scoped); Vorlage = `.env.example`.
- **`anr_app`** darf nur `vereisung` (Least Privilege).

---

## Anhang — DB von Grund auf einrichten (Referenz)

```bash
sudo apt update
sudo apt install -y mariadb-server
sudo systemctl enable --now mariadb
systemctl status mariadb --no-pager        # active (running)?
sudo mariadb-secure-installation
#   root-PW [Enter] · unix_socket Y · change root PW n
#   remove anon Y · disallow root remote Y · remove test-DB Y · reload Y
```
```bash
sudo mariadb        # interaktiv (vermeidet Heredoc-Fallen)
```
```sql
CREATE DATABASE vereisung CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'anr_app'@'localhost' IDENTIFIED BY 'DEIN_ECHTES_PASSWORT';
GRANT ALL PRIVILEGES ON vereisung.* TO 'anr_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```
```bash
mariadb -u anr_app -p -e "SHOW DATABASES;"   # zeigt information_schema + vereisung
```

## Schnellreferenz

| Aktion | Befehl |
|---|---|
| Auf Pi verbinden | `ssh pi@icedetection.local` |
| DB-Konsole | `mariadb -u anr_app -p` |
| User/Rechte | `sudo mariadb -e "SELECT User, Host FROM mysql.user;"` |
| Dienst-Status | `systemctl status mariadb --no-pager` |
| GUI vom Laptop | DBeaver + SSH-Tunnel |
| Backup | `mysqldump vereisung > backup.sql` |
