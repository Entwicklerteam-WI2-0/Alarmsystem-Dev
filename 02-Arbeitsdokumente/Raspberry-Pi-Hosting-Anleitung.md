# Raspberry Pi als Backend-Host — Anleitung

> Ziel: Das Backend auf einem Raspberry Pi im lokalen Netz laufen lassen und per
> VS Code (Remote-SSH) direkt auf dem Pi entwickeln/deployen.

## Wichtig vorab: Was die SSID *nicht* macht

Die **SSID ist nur der Name des WLANs**. Sie verbindet dich **nicht** mit dem Pi —
sie sorgt nur dafür, dass PC und Pi im **selben Netz** hängen. Die eigentliche
Verbindung läuft über **SSH** zur **IP-Adresse** (oder zum Hostnamen) des Pi.

„Hosten" heißt hier: Das Backend läuft als Prozess auf dem Pi und ist über
`http://<pi-ip>:<port>` erreichbar — zunächst nur für Geräte im selben WLAN.

> Empfehlung: Wenn möglich, den Pi per **Ethernet-Kabel** ans Netz hängen statt WLAN.
> Für einen Server ist das stabiler und schneller. WLAN geht, ist aber die schwächere Wahl.

---

## 0. Pi einrichten (falls noch frisch)

Den offiziellen **Raspberry Pi Imager** nutzen. Beim Flashen unter „Edit Settings" direkt setzen:

- **SSH aktivieren** (mit Passwort oder gleich Public Key)
- **WLAN-SSID + Passwort** eintragen (damit der Pi headless ins Netz kommt)
- **Hostname** (z. B. `devpi`) und **Username/Passwort**

Damit ist kein Monitor/keine Tastatur am Pi nötig (headless Setup).

## 1. Pi im Netz finden

```powershell
ping devpi.local        # mDNS-Hostname, oft direkt erreichbar
```

Falls das nicht klappt: IP aus der DHCP-Tabelle des Routers ablesen.

> **Wichtig:** Im Router eine **DHCP-Reservierung** (feste IP) für den Pi setzen.
> Sonst ändert sich die IP irgendwann und VS-Code-Config/Bookmarks brechen.

## 2. SSH-Verbindung (von Windows — ist eingebaut)

```powershell
ssh lucas@devpi.local
# oder: ssh lucas@192.168.x.x
```

Danach SSH-Key statt Passwort einrichten (komfortabler + sicherer):

```powershell
ssh-keygen -t ed25519                       # falls noch kein Key vorhanden
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh lucas@devpi.local "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

## 3. VS Code Remote — der „Remote Explorer"

Der „Remote Explorer" ist die Extension **Remote - SSH** (von Microsoft).

1. In VS Code installieren: Extension **„Remote - SSH"**.
2. `F1` → **Remote-SSH: Add New SSH Host** → `ssh lucas@devpi.local` eingeben →
   speichert einen Eintrag in `~/.ssh/config`.
3. `F1` → **Remote-SSH: Connect to Host** → den Pi wählen.
4. VS Code installiert sich automatisch eine Server-Komponente **auf dem Pi**.
   Du editierst Dateien, hast ein Terminal und debuggst **direkt auf dem Pi**,
   als wäre es lokal.
5. Die **Remote Explorer**-Sidebar (Icon links) listet die Hosts — per Klick verbinden.

`~/.ssh/config` sieht dann z. B. so aus:

```
Host devpi
    HostName devpi.local
    User lucas
    IdentityFile ~/.ssh/id_ed25519
```

## 4. Backend auf den Pi bringen

Sauberster Weg — **direkt auf dem Pi klonen** (im VS-Code-Remote-Terminal):

```bash
git clone <repo-url>
cd <repo>
# Dependencies installieren (stackabhängig)
```

Alternativen: Dateien per Drag & Drop in den VS-Code-Explorer ziehen, oder
`scp`/`rsync` vom PC. **Git ist langfristig am besten**, weil Updates dann nur
`git pull` sind.

## 5. Laufen lassen — und zwar dauerhaft

Erst manuell starten zum Testen. Dann als **Dienst**, damit es nach Logout/Reboot weiterläuft:

- **Node:** `pm2 start ...` (am simpelsten) oder systemd
- **Python/sonstiges:** ein **systemd-Service** (überlebt Reboot, Auto-Restart)

> **Häufige Stolperfalle:** Das Backend muss auf `0.0.0.0` lauschen, **nicht** auf
> `127.0.0.1`/`localhost`. Sonst ist es nur auf dem Pi selbst erreichbar, nicht von
> anderen Geräten im Netz.

Test vom PC: `http://devpi.local:<port>` im Browser.

---

## Vor der Umsetzung klären

Diese drei Punkte entscheiden, ob der Plan so trägt:

1. **Welcher Stack?** Node/Python laufen auf jedem Pi locker. Ein **JVM-Backend
   (Spring Boot)** braucht einen Pi 4/5 mit ausreichend RAM und ist grenzwertig.
   Schwere Cloud-native Stacks (Java reaktiv + DB + Cloud-Dienste) sind **nicht**
   für einen Pi gedacht.
   > **Datenbank (G2-Vorgabe):** Das Backend nutzt **MySQL/MariaDB** (GL-Vorgabe, s. `Backend-Konzept.md §6`).
   > Auf dem Pi **MariaDB** installieren (`sudo apt install mariadb-server`) — der quelloffene, ressourcen-
   > schonende MySQL-Ersatz; als systemd-Dienst dauerhaft. Datenverzeichnis auf stabilem Medium
   > (SD-Karten-Verschleiß bei Dauerschreiblast bedenken; ggf. externe SSD/USB).
2. **Nur im WLAN oder auch von außen (Internet) erreichbar?**
   - Lokales Netz: mit obigem fertig.
   - Von außen: **nicht** über simples Port-Forwarding im Router (Sicherheitsrisiko),
     sondern über **Tailscale** (privates Mesh, am einfachsten) oder
     **Cloudflare Tunnel** (öffentliche URL ohne offene Ports).
3. **Pi-Modell + steht das OS schon?** Bestimmt, ob Schritt 0 nötig ist und welche
   Leistung verfügbar ist.

## Schnellreferenz

| Schritt | Befehl / Aktion |
|---|---|
| Pi finden | `ping devpi.local` |
| Verbinden | `ssh lucas@devpi.local` |
| VS Code | Extension „Remote - SSH" → Connect to Host |
| Code holen | `git clone <repo-url>` (auf dem Pi) |
| Dauerbetrieb | systemd / `pm2` (kein Docker, E-35) |
| Erreichbarkeit | lokal: `http://devpi.local:<port>` · extern: Tailscale / Cloudflare Tunnel |
