"""Wegwerf-Datei nur zum Testen des automatischen Claude-Code-Reviews. Wird nicht gemergt."""


def divide(a, b):
    # absichtlich ohne Division-durch-Null-Behandlung
    return a / b


def get_first(items):
    # greift ohne Leer-Prüfung zu -> IndexError möglich
    return items[0]


PASSWORD = "supersecret123"  # hardcoded secret als Review-Köder
