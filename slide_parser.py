#!/usr/bin/env python3
"""
Slide-Parser v3 (2026-06-08): config-getrieben (pro Genus eine JSON-Config).

Geometrie-Kern UNVERAENDERT aus v1/v2 (parse_slide, cluster_by_y, group_in_row,
detect_syntax, assign_s2_nearest, has_mess_signatur) - der funktionierende Motor.

Generalisierung (v3): alle Genus-/Folien-spezifischen Werte stehen NICHT mehr
im Code, sondern in einer Config (configs/<genus>.json), geladen via --config.
Felder: genus_name, genus_folder, prev_genus_link, merkmal_folien,
folie_zu_art {folie: [oberfamilie, art, art_ordner]}, archiv_map
{folie: [oberfamilie, art]}, extra_folien {folie: [art_ordner, label]}.

Output-Format (MIKRO-Template, Goldstandard 2.1 Aspergillus):
    * H1 = "<Oberfamilie> <Art>  ·  Folie N" (NIE Datum/Mess-ID); roher PPTX-Titel als Callout.
    * Frontmatter: oberfamilie, art, folie, up, prev, next, herkunft, tags (KEIN status).
    * up   -> [[_Übersicht-<Genus>]] (eindeutige Genus-Uebersichtsnote, NIE Ordnername).
    * prev/next -> GLOBAL artuebergreifend in Foliennummer-Reihenfolge (inkl. extra_folien).
    * Footer "## Bilder & Links"; Bilder flach in "8. Bilderarchiv/".

Aufruf:  python slide_parser.py --config configs/aspergillus.json
RUN_FOLIEN (= folie_zu_art ∪ archiv_map) begrenzt den Schreiblauf.
"""

import xml.etree.ElementTree as ET
import json
import shutil
import re
from pathlib import Path
from collections import Counter, defaultdict

# ============================================================
# KONFIGURATION
# ============================================================
PPTX_DIR = Path("C:/Users/LucasVöhringer/Desktop/pptx_extracted")
VAULT_DIR = Path("C:/Users/LucasVöhringer/Desktop/Partikelerkennung-Archiv-Dev/VAULT-Partikelerkennung-Archiv")

SLIDES_DIR = PPTX_DIR / "ppt" / "slides"
SLIDES_RELS_DIR = PPTX_DIR / "ppt" / "slides" / "_rels"
MEDIA_DIR = PPTX_DIR / "ppt" / "media"

BILDERARCHIV = VAULT_DIR / "8. Bilderarchiv"
SPORENARCHIV = VAULT_DIR / "2. Sporenarchiv"
ARCHIV = VAULT_DIR / "9. Archiv"

NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

Y_TOLERANCE = 300000

# ------------------------------------------------------------
# Genus-/Folien-spezifische Werte: NICHT mehr hardcoded, sondern aus
# configs/<genus>.json geladen (siehe load_config). Initial leer; main()
# fuellt sie ueber --config, BEVOR irgendeine Verarbeitung laeuft. Import des
# Moduls (z.B. durch diag_syntax.py) laesst sie leer - der Geometrie-Kern
# braucht sie nicht.
# ------------------------------------------------------------
GENUS_FOLDER = ""          # z.B. "2.1 Aspergillus" (Sektion/Ordner)
GENUS_NAME = ""            # z.B. "Aspergillus" (echte Gattung der Sektion)
GENUS_UEBERSICHT = ""      # "_Übersicht-<GENUS_NAME>" (eindeutige Note, NIE Ordnername)
PREV_GENUS_LINK = ""       # up-Ziel der Genus-Uebersicht (vorherige Genus-Uebersicht; "" = erste)
MERKMAL_FOLIEN = []        # Morphologie-/Merkmalsfolien (Typ E, 0 Bilder) -> Uebersicht
FOLIE_ZU_ART = {}          # folie:int -> (oberfamilie, art, art_ordner)
ARCHIV_MAP = {}            # folie:int -> (oberfamilie, art)  [-> 9. Archiv]
EXTRA_FOLIEN = {}          # folie:int -> (art_ordner, label) [existierend, nicht neu generiert]
FORCE_SYNTAX = {}          # folie:int -> "S2"|"S3"  (per-Folie-Override des TRYB-Diskriminators)


def load_config(path):
    """Laedt eine Genus-Config (JSON) und befuellt die Modul-Globals. JSON-Keys
    (Folien-Nr) sind Strings -> nach int gecastet; Listen -> Tupel (wie der alte
    Hardcode). GENUS_UEBERSICHT wird aus GENUS_NAME abgeleitet."""
    global GENUS_FOLDER, GENUS_NAME, GENUS_UEBERSICHT, PREV_GENUS_LINK
    global MERKMAL_FOLIEN, FOLIE_ZU_ART, ARCHIV_MAP, EXTRA_FOLIEN, SPORENARCHIV, FORCE_SYNTAX
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # base_folder = Ziel-Top-Level. Default "2. Sporenarchiv"; fuer Nicht-Sporen
    # (Pollen/Fasern/Hyphen/Insekten) "1. Keine Sporen".
    SPORENARCHIV = VAULT_DIR / cfg.get("base_folder", "2. Sporenarchiv")
    GENUS_NAME = cfg["genus_name"]
    GENUS_FOLDER = cfg["genus_folder"]
    GENUS_UEBERSICHT = f"_Übersicht-{GENUS_NAME}"
    PREV_GENUS_LINK = cfg.get("prev_genus_link", "")
    MERKMAL_FOLIEN = [int(x) for x in cfg.get("merkmal_folien", [])]
    FOLIE_ZU_ART = {int(k): tuple(v) for k, v in cfg.get("folie_zu_art", {}).items()}
    ARCHIV_MAP = {int(k): tuple(v) for k, v in cfg.get("archiv_map", {}).items()}
    EXTRA_FOLIEN = {int(k): tuple(v) for k, v in cfg.get("extra_folien", {}).items()}
    FORCE_SYNTAX = {int(k): v for k, v in cfg.get("force_syntax", {}).items()}

# ============================================================
# MANIFESTE
# ============================================================

def load_manifests():
    base = Path("C:/Users/LucasVöhringer/Desktop/pptx_bilder_nach_folien/_manifest.json")
    titles = {}
    if base.exists():
        with open(base, 'r', encoding='utf-8') as f:
            for e in json.load(f):
                titles[e['folie']] = e.get('titel', '')
    return titles

# ============================================================
# GEOMETRIE-KERN  (unveraendert aus v1)
# ============================================================

def load_image_map(rels_path):
    if not rels_path.exists():
        return {}
    root = ET.parse(rels_path).getroot()
    return {
        rel.get("Id"): Path(rel.get("Target")).name
        for rel in root.findall(f"{{{NS_RELS}}}Relationship")
        if "image" in rel.get("Type", "")
    }

def get_geom(elem):
    xfrm = elem.find(f".//{{{NS_A}}}xfrm")
    if xfrm is None:
        return None
    off = xfrm.find(f"{{{NS_A}}}off")
    ext = xfrm.find(f"{{{NS_A}}}ext")
    if off is None or ext is None:
        return None
    return {"x": int(off.get("x", 0)), "y": int(off.get("y", 0)),
            "cx": int(ext.get("cx", 0)), "cy": int(ext.get("cy", 0))}

def extract_text(sp_elem):
    return " ".join(t.text for t in sp_elem.iter(f"{{{NS_A}}}t") if t.text).strip()

def parse_slide(slide_num):
    slide_xml = SLIDES_DIR / f"slide{slide_num}.xml"
    rels_xml = SLIDES_RELS_DIR / f"slide{slide_num}.xml.rels"
    if not slide_xml.exists():
        return [], []

    image_map = load_image_map(rels_xml)
    root = ET.parse(slide_xml).getroot()

    images = []
    texts = []

    for pic in root.iter(f"{{{NS_P}}}pic"):
        geom = get_geom(pic)
        if geom is None:
            continue
        blip = pic.find(f".//{{{NS_A}}}blip")
        img_file = None
        if blip is not None:
            embed = blip.get(f"{{{NS_R}}}embed")
            if embed:
                img_file = image_map.get(embed)
        images.append({"type": "image", "file": img_file, **geom})

    for sp in root.iter(f"{{{NS_P}}}sp"):
        if sp.find(f"{{{NS_P}}}txBody") is None:
            continue
        text = extract_text(sp)
        if not text or len(text) < 3:
            continue
        nv = sp.find(f"{{{NS_P}}}nvSpPr")
        if nv is not None:
            nvp = nv.find(f"{{{NS_P}}}nvPr")
            if nvp is not None:
                ph = nvp.find(f"{{{NS_P}}}ph")
                if ph is not None and ph.get("type") == "title":
                    continue
        geom = get_geom(sp)
        if geom:
            texts.append({"type": "text", "text": text, **geom})

    return images, texts

def cluster_by_y(shapes):
    if not shapes:
        return []
    shapes = sorted(shapes, key=lambda s: s["y"])
    rows, current = [], [shapes[0]]
    for s in shapes[1:]:
        if abs(s["y"] - current[-1]["y"]) <= Y_TOLERANCE:
            current.append(s)
        else:
            rows.append(current)
            current = [s]
    rows.append(current)
    return rows

def group_in_row(row):
    row = sorted(row, key=lambda s: s["x"])
    groups, pending = [], []
    for s in row:
        if s["type"] == "image":
            pending.append(s)
        else:
            groups.append({"images": pending.copy(), "text": s})
            pending = []
    return groups, pending

def detect_syntax(groups):
    s3, s2, meta = [], [], []
    for g in groups:
        n = len(g["images"])
        if n >= 2:
            s3.append(g)
        elif n == 1:
            s2.append(g)
        else:
            meta.append(g)
    return s3, s2, meta

def copy_images_to_archiv(images):
    BILDERARCHIV.mkdir(parents=True, exist_ok=True)
    copied = []
    for img in images:
        if not img['file']:
            continue
        src = MEDIA_DIR / img['file']
        dst = BILDERARCHIV / img['file']
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(img['file'])
    return copied

# ============================================================
# TITEL / HERKUNFT / TAGS
# ============================================================

def extract_herkunft(title):
    low = (title or "").lower()
    if 'coburg' in low:
        return 'intern'
    if 'verkauf' in low and 'probe' in low:
        return 'intern'
    return ''

def format_infodaten(raw):
    """Trennt die Infodaten optisch in Zeilen - VERLUSTFREI (fuegt nur <br> ein,
    entfernt/aendert kein Zeichen). Marker: BWB-Dateiname-Ende, Massangaben."""
    t = raw.replace("\n", " ").replace("|", "/")
    # Umbruch nach BWB-Dateiname (endet auf .jpg/.jpeg/.png), wenn Text folgt
    t = re.sub(r'(\.jpe?g|\.png)\s+', r'\1<br>', t, flags=re.IGNORECASE)
    # Umbruch vor Massangaben
    t = re.sub(r'\s+(Größe|Länge|Breite)', r'<br>\1', t)
    return t

def _tagify(s):
    """Obsidian-Tag-safe: klein, keine Klammern, Leerzeichen -> Bindestrich."""
    t = re.sub(r'[()]', '', s.lower())
    t = re.sub(r'\s+', '-', t.strip())
    return t

def build_tags(oberfamilie, art, title):
    low = (title or "").lower()
    tags = []
    of = _tagify(oberfamilie) if oberfamilie else ""
    ar = _tagify(art) if art else ""
    # Rein numerischer Art-Tag (z.B. Typ-Kategorie, art "69") ist als Obsidian-Tag
    # ungueltig -> mit Oberfamilie zu EINEM Tag kombinieren ("typ-69").
    if ar and ar.isdigit() and of:
        tags.append(f"{of}-{ar}")
    else:
        if of:
            tags.append(of)
        if ar:
            tags.append(ar)
    if 'coburg' in low:
        tags.append('hs-coburg')
    return tags

# ============================================================
# MARKDOWN  (nach MIKRO-Template)
# ============================================================

def build_markdown(slide_num, raw_title, s3, s2, meta, unassigned, footer,
                   oberfamilie, art, art_ordner, prev_folie, next_folie):
    L = []
    # #1: monotypisches Genus (art == Gattung) -> art leeren. Verhindert H1
    # "Cladosporium Cladosporium" + Doppel-Tag; H1 faellt auf die Gattung zurueck,
    # der Art-Tag entfaellt, Frontmatter "art:" bleibt leer.
    if art and oberfamilie and art.strip() == oberfamilie.strip():
        art = ""
    herkunft = extract_herkunft(raw_title)
    tags = build_tags(oberfamilie, art, raw_title)

    # Frontmatter
    L.append("---")
    L.append(f"oberfamilie: {oberfamilie}")
    L.append(f"art: {art}")
    L.append(f"folie: {slide_num}")
    L.append(f'up: "[[{GENUS_UEBERSICHT}]]"')
    L.append(f'prev: "[[Folie-{prev_folie:03d}]]"' if prev_folie else 'prev: ""')
    L.append(f'next: "[[Folie-{next_folie:03d}]]"' if next_folie else 'next: ""')
    L.append(f"herkunft: {herkunft}")
    L.append("tags:")
    for t in tags:
        L.append(f"  - {t}")
    L.append("---")
    L.append("")

    # H1 = lesbarer Art-Titel (NIE Datum/Mess-ID) + Folienvermerk
    h1 = f"{oberfamilie} {art}".strip() if art else (oberfamilie or "Unbenannt")
    L.append(f"# {h1}  ·  Folie {slide_num}")
    L.append("")

    # Roher PPTX-Titel als Beleg (bewahrt IDs/Kommentare, ohne H1 zu verschmutzen)
    if raw_title:
        L.append("> [!quote]- PPTX-Titel")
        L.append(f"> {raw_title}")
        L.append("")

    # Breadcrumb-Navigation (Publish-sichtbar): prev | Genus-Uebersicht | next.
    # prev/next artenuebergreifend; up zeigt auf die Genus-Uebersicht, nie auf den eigenen Ordner.
    crumb = []
    if prev_folie:
        crumb.append(f"[[Folie-{prev_folie:03d}|← Folie {prev_folie}]]")
    crumb.append(f"[[{GENUS_UEBERSICHT}|↑ {GENUS_NAME}]]")
    if next_folie:
        crumb.append(f"[[Folie-{next_folie:03d}|Folie {next_folie} →]]")
    L.append(" | ".join(crumb))
    L.append("")
    L.append("---")
    L.append("")

    # Syntax3: 3-Spalten
    if s3:
        L.append("|       Mikro-Bild       |        BWB-Bild        | Infodaten |")
        L.append("| :--------------------: | :--------------------: | :-------- |")
        for g in s3:
            imgs = g["images"]
            txt = format_infodaten(g["text"]["text"])
            micro = f"![[{imgs[0]['file']}\\|150]]" if imgs[0]['file'] else "—"
            bwb = f"![[{imgs[1]['file']}\\|150]]" if len(imgs) > 1 and imgs[1]['file'] else "—"
            L.append(f"| {micro} | {bwb} | {txt} |")
        L.append("")

    # Syntax2: 2-Spalten
    if s2:
        L.append("|       Mikro-Bild       | Infodaten |")
        L.append("| :--------------------: | :-------- |")
        for g in s2:
            imgs = g["images"]
            txt = format_infodaten(g["text"]["text"])
            micro = f"![[{imgs[0]['file']}\\|150]]" if imgs and imgs[0]['file'] else "—"
            L.append(f"| {micro} | {txt} |")
        L.append("")

    # Meta-Texte (ohne Bild)
    for g in meta:
        txt = g["text"]["text"].replace("\n", " ")
        L.append(f"> [!info] {txt}")
        L.append("")

    # Footer
    L.append("---")
    L.append("")
    L.append("## Bilder & Links")
    L.append("")
    L.append("Hier werden Links zur Literatur (in der PPTX LETZTE Kategorie) und weitere "
             "Bilder zum Genus, die keiner eindeutigen Messung zugeordnet werden, abgelegt.")
    L.append("")
    # Footer-/Mass-Kommentare (1:1 erhalten, aber raus aus der Mess-Tabelle)
    for ft in footer:
        L.append(f"> [!note] {ft['text'].strip()}")
        L.append("")

    # Zusaetzliche Bilder (ohne eindeutige Zuordnung)
    if unassigned:
        L.append("---")
        L.append("")
        L.append("> [!note] zusätzliche Bilder")
        L.append(">")
        L.append("> | Mikro-Bild | BWB-Bild | Kommentar |")
        L.append("> |---|---|---|")
        i = 0
        while i < len(unassigned):
            a = unassigned[i]
            b = unassigned[i + 1] if i + 1 < len(unassigned) else None
            micro = f"![[{a['file']}\\|150]]" if a['file'] else "—"
            bwb = f"![[{b['file']}\\|150]]" if b and b['file'] else "—"
            L.append(f"> | {micro} | {bwb} | — |")
            i += 2
        L.append("")

    return "\n".join(L)

# ============================================================
# VERARBEITUNG
# ============================================================

def has_mess_signatur(text):
    """Ein echter Mess-Text traegt eine Mess-Signatur: Dateiname (.jpg/.jpeg/.png),
    Koordinate (Line-, x..-y..), Mess-ID (ID-, TRYB) oder lange Mess-Nummer (5+ Ziffern).
    Texte OHNE solche Signatur sind Labels/Kommentare (z.B. 'Typ 08', Mass-Hinweise)
    und gehoeren NICHT in die Mess-Tabelle. Deckt ~99% ab (Rest: manueller Review)."""
    t = (text or "").lower()
    return bool(re.search(r'\.jpe?g|\.png|line[- ]|tryb|id-|x\d+-y|\d{5,}', t))

def is_s3_folie(texts):
    """Dominanter Syntax pro Folie (Lucas-Architektur): S3 <=> 'TRYB' in IRGENDEINEM
    Infotext, sonst S2. S2 und S3 treten NIE auf derselben Folie auf. TRYB ist das
    feste Kennzeichen von S3; S2 ist heterogen (mal .jpg, mal Mess-ID) -> per Default."""
    return any('tryb' in (t.get('text', '') or '').lower() for t in texts)

def assign_s2_nearest(images, texts):
    """S2-Zuordnung: jedem Mess-Text das raeumlich naechste FREIE Bild zuordnen
    (euklidische x/y-Distanz der Shape-Positionen, folienweit). Loest Text-ohne-Bild
    und Bild-ohne-Text ueber Zeilengrenzen hinweg. Greedy, Texte nach (y,x) stabil.
    Uebrige Bilder -> Zusatz; uebrige Texte (mehr Texte als Bilder) -> Zeile ohne Bild."""
    free = list(images)
    pairs = []
    for t in sorted(texts, key=lambda s: (s["y"], s["x"])):
        if free:
            best = min(free, key=lambda im: (im["x"] - t["x"]) ** 2 + (im["y"] - t["y"]) ** 2)
            free.remove(best)
            pairs.append({"images": [best], "text": t})
        else:
            pairs.append({"images": [], "text": t})
    return pairs, free

def parse_and_classify(slide_num, title=""):
    """Parst eine Folie geometrisch und liefert die Tabellen-Bausteine (ohne prev/next).
    Dominanter Syntax pro Folie (TRYB). S3: group_in_row (Bilder bis Text sammeln,
    Mikro+BWB-Paar). S2: nearest (1 Mikro je Text, folienweit)."""
    images, texts = parse_slide(slide_num)
    if not images and not texts:
        return None
    copied = copy_images_to_archiv(images)

    # Texte klassifizieren: Mess-Texte (mit Signatur) vs Labels/Kommentare.
    title_norm = (title or "").strip().lower()
    mess_texts, footer = [], []
    for t in texts:
        s = (t["text"] or "").strip()
        if has_mess_signatur(s):
            mess_texts.append(t)
        elif s and s.lower() != title_norm:
            footer.append(t)          # Kommentar/Mass-Hinweis -> "Bilder & Links"
        # Titel-Duplikat (Label, z.B. "Typ 08") -> ganz weg (steht schon im H1)
    texts = mess_texts

    # Per-Folie-Override (Config force_syntax) schlaegt den TRYB-Diskriminator.
    # Default leer -> Verhalten unveraendert.
    if slide_num in FORCE_SYNTAX:
        is_s3 = (FORCE_SYNTAX[slide_num].upper() == "S3")
    else:
        is_s3 = is_s3_folie(texts)
    s3, s2, meta, unassigned = [], [], [], []
    if is_s3:
        # S3: Bilder bis Text sammeln (Mikro+BWB-Paar). Geometrie pro Zeile.
        for row in cluster_by_y(images + texts):
            groups, pending = group_in_row(row)
            unassigned.extend(pending)
            for g in groups:
                (s3 if g["images"] else meta).append(g)
    else:
        # S2: jedem Text das naechste Bild (x/y), folienweit.
        s2, unassigned = assign_s2_nearest(images, texts)
    return {"s3": s3, "s2": s2, "meta": meta, "unassigned": unassigned,
            "footer": footer, "copied": copied, "syntax": "S3" if is_s3 else "S2"}

# PREV_GENUS_LINK (up-Ziel) + EXTRA_FOLIEN (existierende, nicht neu generierte Folien
# fuers Inhaltsverzeichnis, z.B. Negativbeispiel-Folie) kommen jetzt aus der Config
# (load_config). EXTRA_FOLIEN ist zugleich Teil der prev/next-Kette (siehe main).

def build_genus_uebersicht(parsed):
    """Generiert die Genus-Uebersichtsnote (= Folder-Note, Dateiname = Ordnername).
    F29-Merkmale + annotiertes Inhaltsverzeichnis (nach Art gruppiert) + Kommentarsektion."""
    L = []
    merkmale = []
    for mf in MERKMAL_FOLIEN:
        _, mtexts = parse_slide(mf)
        merkmale.extend(t["text"].strip() for t in mtexts if t["text"].strip())

    herkuenfte = sorted({h for d in parsed.values() if (h := extract_herkunft(d["title"]))})

    L.append("---")
    L.append(f"oberfamilie: {GENUS_NAME}")
    L.append("art:")
    L.append(f'up: "{PREV_GENUS_LINK}"')
    L.append(f"herkunft: {', '.join(herkuenfte)}")
    L.append("tags:")
    L.append(f"  - {GENUS_NAME.lower()}")
    L.append("  - meta/genus-uebersicht")
    L.append("---")
    L.append("")
    L.append(f"# {GENUS_NAME}")
    L.append("")
    L.append(f"> Genus-Übersicht **{GENUS_NAME}** — Inhaltsverzeichnis der Arten & Folien.")
    L.append(f"> Hier steht außerdem, welche Sporen **nicht** als {GENUS_NAME} zu labeln sind.")
    L.append("")
    L.append("## Merkmale und Besonderheiten")
    L.append("")
    if merkmale:
        for m in merkmale:
            L.append(f"- {m}")
    else:
        L.append("*(noch zu ergänzen)*")
    L.append("")
    L.append("## Folien")
    L.append("")
    # nach Art-Ordner gruppieren (nur Sporen), + Extra-Folien (z.B. 9 Negativbeispiel)
    by_ordner = defaultdict(list)
    for f, d in parsed.items():
        if d["ziel"] == "sporen":
            n_mess = len(d["s3"]) + len(d["s2"])
            by_ordner[d["ordner"]].append((f, f"{n_mess} Messungen"))
    for f, (ordner, label) in EXTRA_FOLIEN.items():
        by_ordner[ordner].append((f, label))
    genus_praefix = GENUS_FOLDER.split()[0]   # z.B. "2.1" aus "2.1 Aspergillus"
    def ordner_num(o):
        m = re.match(rf'{re.escape(genus_praefix)}\.(\d+)', o)
        return int(m.group(1)) if m else 999
    for ordner in sorted(by_ordner.keys(), key=ordner_num):
        if ordner:                      # monotypisch: ordner == "" -> keine Art-Zwischenueberschrift
            L.append(f"### {ordner}")
        for f, label in sorted(by_ordner[ordner]):
            L.append(f"- [[Folie-{f:03d}]] — {label}")
        L.append("")
    L.append("## Kommentarsektion")
    L.append("")
    L.append("> [!note] Kommentare der Mikrobiologie")
    L.append("> *(Hier kann die Chef-Editorin bei Übergabe Kommentare zu den Messungen hinterlegen.)*")
    L.append("")
    return "\n".join(L)

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Slide-Parser v3 (config-getrieben)")
    ap.add_argument("--config", required=True, help="Pfad zur Genus-Config (JSON)")
    args = ap.parse_args()
    load_config(args.config)

    run_folien = sorted(set(FOLIE_ZU_ART.keys()) | set(ARCHIV_MAP.keys()))

    print("=" * 70)
    print(f"Slide-Parser v3 | Genus: {GENUS_NAME} | Config: {args.config}")
    print(f"RUN_FOLIEN = {run_folien}")
    print("=" * 70)

    titles = load_manifests()
    if not titles:
        print("FEHLER: Kein Manifest gefunden!")
        return

    # Pass 1: parsen + klassifizieren (FOLIE_ZU_ART -> Sporenarchiv, ARCHIV_MAP -> 9. Archiv)
    parsed = {}
    for f in run_folien:
        if f in FOLIE_ZU_ART:
            ob, art, ordner = FOLIE_ZU_ART[f]
            # #3: monotypisches Genus (art == Gattung) -> kein redundanter Art-Unterordner.
            # Folios direkt in den Genus-Ordner; _Übersicht- floatet dann per Unterstrich
            # nach oben (Obsidian listet Ordner zuerst -> ohne Unterordner steht die Datei oben).
            if art and art.strip() == ob.strip():
                ordner = ""
            ziel = "sporen"
        elif f in ARCHIV_MAP:
            ob, art = ARCHIV_MAP[f]
            ordner = "9. Archiv"
            ziel = "archiv"
        else:
            print(f"Folie {f}: SKIP (kein Mapping)")
            continue
        data = parse_and_classify(f, titles.get(f, ""))
        if data is None:
            print(f"Folie {f}: SKIP (keine Shapes)")
            continue
        data.update({"oberfamilie": ob, "art": art, "ordner": ordner,
                     "title": titles.get(f, ""), "ziel": ziel})
        parsed[f] = data

    # prev/next: GLOBAL ueber alle Sporen-Folien des Genus in Foliennummer-Reihenfolge
    # (artenuebergreifend, auch an Art-Raendern). Folie 9 (Negativbeispiel, existiert,
    # nicht neu generiert) ist Teil der Kette. Archiv-Folien bleiben aussen vor.
    sporen = sorted(set(f for f, d in parsed.items() if d["ziel"] == "sporen") | set(EXTRA_FOLIEN.keys()))
    prevnext = {}
    for i, f in enumerate(sporen):
        p = sporen[i - 1] if i > 0 else None
        n = sporen[i + 1] if i + 1 < len(sporen) else None
        prevnext[f] = (p, n)
    for f, d in parsed.items():
        if d["ziel"] == "archiv":
            prevnext[f] = (None, None)

    # Pass 2: Markdown bauen + schreiben
    stats = Counter()
    for f, d in parsed.items():
        p, n = prevnext.get(f, (None, None))
        md = build_markdown(f, d["title"], d["s3"], d["s2"], d["meta"], d["unassigned"],
                            d["footer"], d["oberfamilie"], d["art"], d["ordner"], p, n)
        out_dir = ARCHIV if d["ziel"] == "archiv" else (SPORENARCHIV / GENUS_FOLDER / d["ordner"])
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"Folie-{f:03d}.md"
        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"Folie {f:3d}: -> {d['ordner']}/Folie-{f:03d}.md "
              f"| S3:{len(d['s3'])} S2:{len(d['s2'])} | {len(d['copied'])} Bilder")
        stats["geschrieben"] += 1

    # Genus-Uebersichtsnote (Folder-Note = Ordnername, fuer up-Ziel + Inhaltsverzeichnis)
    uebersicht_file = SPORENARCHIV / GENUS_FOLDER / f"{GENUS_UEBERSICHT}.md"
    with open(uebersicht_file, "w", encoding="utf-8") as fh:
        fh.write(build_genus_uebersicht(parsed))
    print(f"\nGenus-Uebersicht: -> {GENUS_FOLDER}/{GENUS_UEBERSICHT}.md")

    print("\n" + "=" * 70)
    for s, c in stats.items():
        print(f"  {s}: {c}")


if __name__ == "__main__":
    main()
