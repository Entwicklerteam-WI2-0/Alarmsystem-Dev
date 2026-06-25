"""Tests für den No-Hardcode-Schwellen-Guard (DTB-22, NF-05).

Der Guard schützt die künftige Bewertungslogik (assessment/forecast) davor, dass
Schwellenwerte als Literal in den Code wandern, statt aus `config/` geladen zu werden.
Erkennung über den AST — die Snippets sind daher gültiges Python (wie echte Dateien).
"""

from tools.check_hardcoded_thresholds import finde_verstoesse, main, pruefe_verzeichnisse


def _scan(quelltext: str):
    return finde_verstoesse(quelltext, "assessment/core.py")


def test_default_ziele_sind_skript_relativ():
    # SCAN_DIRS wird relativ zum Skript (04-Source-code) aufgelöst -> cwd-unabhängig,
    # damit pre-commit ohne Pfad-Argumente laufen kann (eine Quelle der Wahrheit).
    from tools.check_hardcoded_thresholds import _default_ziele

    ziele = [z.replace("\\", "/") for z in _default_ziele()]
    assert len(ziele) == 2
    assert all(z.endswith(("src/assessment", "src/forecast")) for z in ziele)
    assert all("04-Source-code" in z for z in ziele)


# --- Positivfälle: müssen erkannt werden (DoD-Beispiele '> 1.0', '< 0.0', 'delta_T <= 1.0') ---


def test_groesser_literal_wird_erkannt():
    verstoesse = _scan("if t_s > 1.0:\n    pass\n")
    assert len(verstoesse) == 1
    assert verstoesse[0].zeile == 1


def test_kleiner_null_wird_erkannt():
    assert _scan("if t_s < 0.0:\n    pass\n")


def test_delta_t_vergleich_wird_erkannt():
    assert _scan("if delta_t <= 1.0:\n    pass\n")


def test_delta_t_grossschreibung_wird_erkannt():
    assert _scan("if delta_T <= 1.0:\n    pass\n")


def test_literal_links_wird_erkannt():
    # umgekehrte Richtung: 0.0 < t_s
    assert _scan("if 0.0 < t_s:\n    pass\n")


def test_groesser_gleich_ganzzahl_wird_erkannt():
    assert _scan("risk = 'rot' if t_s >= 0 else 'gruen'\n")


def test_gleichheits_vergleich_gegen_literal_wird_erkannt():
    # delta_t == 0.0: die 0.0 ist der Config-Wert delta_t_kondensation_k -> gehört nach config/.
    assert _scan("if delta_t == 0.0:\n    pass\n")


def test_ungleichheits_vergleich_gegen_literal_wird_erkannt():
    assert _scan("if t_s != 0.0:\n    pass\n")


def test_float_ohne_fuehrende_null_wird_erkannt():
    # `.5` ist ein gültiges Float-Literal und muss erkannt werden.
    assert _scan("if t_s > .5:\n    pass\n")


def test_negatives_literal_wird_erkannt():
    # Vorzeichen: -2.1 ist im AST ein UnaryOp(USub, Constant) — muss trotzdem zählen.
    assert _scan("if t_s > -2.1:\n    pass\n")


def test_mehrere_zeilen_mehrere_verstoesse():
    verstoesse = _scan("a = t_s > 1.0\nb = delta_t <= 1.0\n")
    assert [v.zeile for v in verstoesse] == [1, 2]


def test_zwei_vergleiche_eine_zeile_beide_gemeldet():
    # Vollständigkeit: zwei echte Vergleiche auf einer Zeile -> beide gemeldet (M4).
    verstoesse = _scan("if t_s > 1.0 and delta_t < 0.0:\n    pass\n")
    assert [v.zeile for v in verstoesse] == [1, 1]


# --- Durch AST neu geschlossene Fälle (vorher Regex-Grenzen) ---


def test_mehrzeiliger_vergleich_wird_erkannt():
    # Operator und Literal auf verschiedenen Zeilen — AST sieht die Struktur.
    assert _scan("if (\n    t_s > 1.0\n):\n    pass\n")


def test_vergleich_in_fstring_wird_erkannt():
    assert _scan('label = f"{1 if t_s > 1.0 else 0}"\n')


def test_indirekter_vergleich_operator_gt_wird_erkannt():
    assert _scan("import operator\nif operator.gt(t_s, 1.0):\n    pass\n")


def test_indirekter_vergleich_math_isclose_wird_erkannt():
    assert _scan("import math\nif math.isclose(t_s, 0.0):\n    pass\n")


def test_isclose_toleranz_kwarg_ist_kein_fehlalarm():
    # L6: rel_tol/abs_tol sind Toleranzen, keine Schwellen -> nicht flaggen.
    assert _scan("import math\nif math.isclose(t_s, x, rel_tol=0.01):\n    pass\n") == []


def test_isclose_abs_tol_kwarg_ist_kein_fehlalarm():
    # abs_tol ist ebenfalls eine Toleranz (eigener Negativfall, sichert _TOLERANZ_KWARGS ab).
    assert _scan("import math\nif math.isclose(t_s, x, abs_tol=0.01):\n    pass\n") == []


def test_bool_literal_im_vergleich_ist_kein_fehlalarm():
    # bool ist Unterklasse von int — `flag > True` darf NICHT als Schwellen-Literal zählen.
    assert _scan("if flag > True:\n    pass\n") == []


def test_isclose_keyword_vergleichswert_wird_erkannt():
    # B-1: math.isclose(a=t_s, b=0.0) — b=0.0 ist ein Vergleichswert (kein Toleranz-Kwarg).
    assert _scan("import math\nif math.isclose(a=t_s, b=0.0):\n    pass\n")


def test_verkettete_vergleiche_zaehlen_als_ein_befund():
    # A-2: 0.0 < t_s < 1.0 ist EIN ast.Compare-Knoten -> ein Befund (genügt fürs Gate).
    verstoesse = _scan("if 0.0 < t_s < 1.0:\n    pass\n")
    assert len(verstoesse) == 1


# --- Negativfälle: dürfen NICHT erkannt werden (kein Fehlalarm) ---


def test_vergleich_gegen_config_variable_ist_sauber():
    assert _scan("if t_s > schwellen.t_s_gefrierpunkt_c:\n    pass\n") == []


def test_reiner_kommentar_wird_ignoriert():
    assert _scan("# Beispiel: if t_s > 1.0\n") == []


def test_inline_kommentar_mit_literal_wird_ignoriert():
    assert _scan("x = berechne()  # frueher: t_s > 1.0\n") == []


def test_escape_marker_unterdrueckt_treffer():
    assert _scan("if t_s > 1.0:  # noqa: hardcoded-threshold\n    pass\n") == []


def test_zuweisung_ohne_vergleich_ist_sauber():
    assert _scan("delta_t = t_s - t_d\n") == []


def test_docstring_einzeilig_wird_ignoriert():
    assert _scan('"""Gibt ROT, wenn t_s > 1.0 und delta_t <= 1.0."""\n') == []


def test_docstring_mehrzeilig_wird_ignoriert():
    assert _scan('"""\nKaskade:\n  t_s > 1.0 -> pruefen\n"""\nx = 1\n') == []


def test_string_literal_mit_muster_wird_ignoriert():
    assert _scan('raise ValueError("delta_t > 1.0 ist ungueltig")\n') == []


def test_beliebiger_methodenaufruf_mit_literal_ist_sauber():
    # Nur operator.*/math.isclose zählen als indirekter Vergleich — ein gewöhnlicher
    # Attribut-Methodenaufruf mit Zahl-Argument (z. B. wert.quantize(2)) ist keiner.
    assert _scan("x = zustand.quantize(t_s, 2.0)\n") == []


def test_escaped_quote_im_string_kein_fehlalarm():
    # AST kennt String-Grenzen — kein Fehlalarm mehr (frühere Regex-Schwäche).
    assert _scan('msg = "er sagte \\"t_s > 1.0\\" laut"\n') == []


def test_range_und_index_sind_sauber():
    assert _scan("for i in range(0, 10):\n    x = werte[2]\n") == []


def test_return_annotation_pfeil_ist_kein_fehlalarm():
    # Das '>' in '->' darf nicht als Vergleich gegen ein Literal zählen.
    assert _scan("def bewerte(t_s: float) -> int:\n    return 0\n") == []


def test_marker_im_string_unterdrueckt_echten_verstoss_nicht():
    # Ein String mit dem Markertext darf einen echten Verstoß NICHT unterdrücken —
    # nur ein echter Kommentar darf das.
    assert _scan('msg = "noqa: hardcoded-threshold"; bug = t_s > 1.0\n')


def test_noqa_auf_anderer_zeile_unterdrueckt_nicht():
    # H2: ein noqa, das nicht auf der Vergleichszeile steht, darf den Verstoß nicht
    # verstecken. Hier steht der Vergleich auf Zeile 1, das noqa auf Zeile 2.
    assert _scan("if t_s > (\n    1.0):  # noqa: hardcoded-threshold\n    pass\n")


def test_marker_mit_suffix_unterdrueckt_nicht():
    # L7: '# noqa: hardcoded-threshold-OFF' ist NICHT der Marker -> Verstoß bleibt bestehen.
    assert _scan("if t_s > 1.0:  # noqa: hardcoded-threshold-OFF\n    pass\n")


def test_marker_mit_praefix_unterdrueckt_nicht():
    # Boundary auch links: '# x-noqa: hardcoded-threshold' ist NICHT der Marker -> Verstoß bleibt.
    assert _scan("if t_s > 1.0:  # x-noqa: hardcoded-threshold\n    pass\n")


# --- Dokumentierte verbleibende Grenze (Datenfluss, bewusst nicht erkannt) ---


def test_schwelle_in_variable_bleibt_dokumentierte_grenze():
    # `grenze = 1.0` + `t_s > grenze`: kein Literal IM Vergleich -> Code-Review ist 2. Instanz.
    assert _scan("grenze = 1.0\nif t_s > grenze:\n    pass\n") == []


# --- Robustheit ---


def test_syntaxfehler_ist_fail_closed():
    # C1: nicht parsebarer Code darf nicht crashen UND nicht still "OK" liefern —
    # er wird als Verstoß gemeldet (Gate fail-closed).
    verstoesse = finde_verstoesse("def kaputt(:\n", "x.py")
    assert len(verstoesse) == 1
    assert "parsebar" in verstoesse[0].grund


def test_fail_closed_feld_unterscheidet_fundart():
    # Der Behebungs-Hinweis hängt am expliziten Feld, NICHT am Grund-Text — sonst bräche
    # die Zweig-Auswahl bei einer Umformulierung des Grund-Textes lautlos.
    schwelle = finde_verstoesse("if t_s > 1.0:\n    pass\n", "x.py")
    assert schwelle[0].fail_closed is False
    syntax = finde_verstoesse("def kaputt(:\n", "x.py")
    assert syntax[0].fail_closed is True


# --- Verzeichnis-Walk + Verstoss-Felder ---


def test_pruefe_verzeichnis_findet_datei(tmp_path):
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    verstoesse = pruefe_verzeichnisse([d])
    assert len(verstoesse) == 1
    assert verstoesse[0].datei.endswith("core.py")
    assert verstoesse[0].zeile == 1


def test_pruefe_verzeichnis_sauber_gibt_leer(tmp_path):
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text(
        "if t_s > schwellen.t_s_gefrierpunkt_c:\n    pass\n", encoding="utf-8"
    )
    assert pruefe_verzeichnisse([d]) == []


def test_bom_datei_wird_geprueft(tmp_path):
    # C1: eine Datei mit UTF-8-BOM (Windows-Editoren) darf das Gate nicht still grün
    # lassen — der Verstoß muss trotz BOM erkannt werden (utf-8-sig).
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_bytes(b"\xef\xbb\xbfif t_s > 1.0:\n    pass\n")
    verstoesse = pruefe_verzeichnisse([d])
    assert len(verstoesse) == 1


def test_nicht_existierendes_verzeichnis_wird_uebersprungen():
    assert pruefe_verzeichnisse(["gibt/es/nicht"]) == []


def test_non_utf8_datei_crasht_nicht(tmp_path):
    # Eine Latin-1-Datei darf das Gate nicht mit UnicodeDecodeError abbrechen;
    # der Verstoß muss trotzdem erkannt werden (errors="replace").
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_bytes("if t_s > 1.0:  # \xfcber\n    pass\n".encode("latin-1"))
    verstoesse = pruefe_verzeichnisse([d])
    assert len(verstoesse) == 1


# --- CLI-Gate: Exit-Codes (das eigentliche Gate-Verhalten) ---


def test_main_sauber_gibt_exit_null(tmp_path, capsys):
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text(
        "if t_s > schwellen.t_s_gefrierpunkt_c:\n    pass\n", encoding="utf-8"
    )
    code = main([str(d)])
    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_main_verstoss_gibt_exit_eins(tmp_path, capsys):
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "FEHLER" in ausgabe
    assert "core.py" in ausgabe


def test_main_verstoss_unterdrueckt_stub_hinweis(tmp_path, capsys):
    # Regression: ein Verstoß (auch in __init__.py) darf nicht zugleich den
    # "nur Stubs"-HINWEIS auslösen — das wäre eine widersprüchliche Meldung.
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "__init__.py").write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "FEHLER" in ausgabe
    assert "HINWEIS" not in ausgabe


def test_main_nur_stubs_zeigt_hinweis(tmp_path, capsys):
    # Sauberer Lauf über nur __init__.py (noch keine Bewertungslogik) -> Exit 0 + HINWEIS.
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "__init__.py").write_text('"""Stub."""\n', encoding="utf-8")
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "HINWEIS" in ausgabe


def test_main_alle_verzeichnisse_fehlen_ist_fail_closed(capsys):
    # Existiert KEIN Scan-Ziel, darf der Guard nicht still grün melden -> Exit 1.
    code = main(["gibt/es/nicht"])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "FEHLER" in ausgabe
    assert "fail-closed" in ausgabe


def test_main_teilweise_fehlend_warnt_und_laeuft_weiter(tmp_path, capsys):
    # Mind. ein Ziel existiert (sauber) -> nur WARNUNG fürs fehlende, Exit 0.
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text(
        "if t_s > schwellen.t_s_gefrierpunkt_c:\n    pass\n", encoding="utf-8"
    )
    code = main([str(d), str(tmp_path / "gibt-es-nicht")])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "WARNUNG" in ausgabe
    assert "OK" in ausgabe


def test_main_leeres_verzeichnis_ist_fail_closed(tmp_path, capsys):
    # Existierendes, aber leeres Verzeichnis (0 .py) -> nichts geprüft -> Exit 1.
    d = tmp_path / "assessment"
    d.mkdir()
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "fail-closed" in ausgabe


def test_main_nicht_py_datei_als_arg_ist_fail_closed(tmp_path, capsys):
    # Eine existierende Nicht-.py-Datei ist nichts Prüfbares -> fail-closed (nicht still grün).
    f = tmp_path / "notiz.txt"
    f.write_text("if t_s > 1.0: egal\n", encoding="utf-8")
    code = main([str(f)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "fail-closed" in ausgabe


def test_main_nicht_py_datei_neben_gueltigem_ziel_wird_gemeldet(tmp_path, capsys):
    # Existierende Nicht-.py-Datei neben gültigem Ziel darf nicht still verschluckt werden:
    # sichtbare WARNUNG, kein lautloses Übergehen (Safety-Gate: lieber laut als still).
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("if t_s > schw.x:\n    pass\n", encoding="utf-8")
    notiz = tmp_path / "notiz.txt"
    notiz.write_text("egal\n", encoding="utf-8")
    code = main([str(d), str(notiz)])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "WARNUNG" in ausgabe
    assert "notiz.txt" in ausgabe


def test_main_unlesbare_datei_ist_fail_closed(tmp_path, monkeypatch, capsys):
    # Eine nicht lesbare Datei (PermissionError) darf nicht mit Traceback crashen,
    # sondern fail-closed melden (analog SyntaxError).
    import pathlib

    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("x = 1\n", encoding="utf-8")
    original = pathlib.Path.read_text

    def kein_zugriff(self, *args, **kwargs):
        if self.name == "core.py":
            raise PermissionError("kein Zugriff")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", kein_zugriff)
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "nicht lesbar" in ausgabe
    assert "fail-closed" in ausgabe


def test_main_datei_als_argument_wird_geprueft(tmp_path, capsys):
    # Eine .py-Datei direkt als Argument muss gescannt werden (nicht still grün).
    f = tmp_path / "core.py"
    f.write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    code = main([str(f)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "FEHLER" in ausgabe
    assert "core.py" in ausgabe


def test_main_syntaxfehler_meldung_raet_zu_reparatur(tmp_path, capsys):
    # Bei einer nicht parsebaren Datei ist „config/ laden/noqa" falscher Rat -> Reparatur-Hinweis.
    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("def kaputt(:\n", encoding="utf-8")
    code = main([str(d)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "beheben" in ausgabe  # Reparatur-Hinweis (Syntax/Encoding/Berechtigung)
    assert "Schwellen über config/ laden" not in ausgabe


def test_main_ausgabe_crasht_nicht_auf_cp1252(tmp_path):
    # Regression: die Ausgabe (inkl. „→"/Umlaute) darf auf einer cp1252-Konsole
    # (Windows-Default) nicht mit UnicodeEncodeError crashen.
    import io
    import sys

    d = tmp_path / "assessment"
    d.mkdir()
    (d / "core.py").write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    alt = sys.stdout
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    try:
        code = main([str(d)])  # darf nicht mit UnicodeEncodeError crashen
    finally:
        sys.stdout = alt
    assert code == 1


def test_main_duplikat_argument_einmal_gemeldet(tmp_path, capsys):
    # Dieselbe Datei zweimal als Argument -> Verstoß nur EINMAL gemeldet (Dedup).
    f = tmp_path / "core.py"
    f.write_text("if t_s > 1.0:\n    pass\n", encoding="utf-8")
    code = main([str(f), str(f)])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "1 Verstoß" in ausgabe


def test_isclose_kwargs_entpackung_kein_fehlalarm():
    # kw.arg is None bei **tol-Entpackung -> übersprungen, kein Kandidat, kein Fehlalarm.
    assert _scan("import math\ntol = {}\nif math.isclose(t_s, x, **tol):\n    pass\n") == []
