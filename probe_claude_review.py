"""Wegwerf-Datei nur zum Testen des automatischen Claude-Code-Reviews. Wird nicht gemergt."""


def divide(a, b):
    # absichtlich ohne Division-durch-Null-Behandlung, damit das Review etwas zu sagen hat
    return a / b


def get_first(items):
    # greift ohne Leer-Prüfung zu
    return items[0]
