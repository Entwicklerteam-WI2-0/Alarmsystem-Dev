"""Wegwerf-Datei zum Testen des automatischen Claude-Code-Reviews. Wird nicht gemergt."""


def divide(a, b):
    return a / b  # keine Division-durch-Null-Behandlung


def get_first(items):
    return items[0]  # IndexError bei leerer Liste möglich


PASSWORD = "supersecret123"  # hardcoded secret als Review-Köder
