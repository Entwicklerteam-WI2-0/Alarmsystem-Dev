"""Zentrale, fachliche Konstanten des G2-Backends (NF-05).

Diese Werte sind zunaechst Konstanten, koennen aber bei Bedarf
(z. B. F24/Geo) in eine parametrierbare Config ausgelagert werden.
"""

# Single-Sensor-Betrieb bis F24/Geo. Wird im Poller (main.py) und im
# Historien-Endpoint (api/v1.py) verwendet, um Drift zwischen den
# beiden Stellen zu vermeiden.
DEFAULT_SENSOR_ID = "anr-rwy-01"
