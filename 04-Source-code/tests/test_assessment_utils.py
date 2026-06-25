"""Tests fuer die Taupunktberechnung (Magnus-Formel, DTB-32).

Magnus-Parameter (a=17,62; b=243,12 °C) stammen aus Schwellenwerte.md §1.
Die Referenzwerte sind unabhaengig nachgerechnet; die Toleranz ist eng (abs=1e-2),
damit ein Vorzeichen-/Konstantenfehler nicht maskiert wird. Nichts dazuerfunden.
"""

import math

import pytest

from src.assessment.utils import calculate_dew_point


def test_taupunkt_gleich_lufttemperatur_bei_saettigung_20c() -> None:
    # Arrange: bei 100 % Luftfeuchte ist der Taupunkt gleich der Lufttemperatur.
    air_temp_c = 20.0
    humidity_pct = 100.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert (analytisch exakt -> sehr enge Toleranz)
    assert dew_point_c == pytest.approx(20.0, abs=1e-6)


def test_taupunkt_gleich_lufttemperatur_bei_saettigung_0c() -> None:
    # Arrange: Saettigung am Gefrierpunkt -> Taupunkt = 0 °C.
    air_temp_c = 0.0
    humidity_pct = 100.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(0.0, abs=1e-6)


def test_taupunkt_referenz_20c_60prozent() -> None:
    # Arrange: Ticket-Referenz DTB-32 (T_a=20 °C, RH=60 % -> T_d = 11,995 °C).
    air_temp_c = 20.0
    humidity_pct = 60.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(11.995, abs=1e-2)


def test_taupunkt_referenz_25c_50prozent() -> None:
    # Arrange: meteorologischer Standardwert (T_a=25 °C, RH=50 % -> T_d = 13,852 °C).
    air_temp_c = 25.0
    humidity_pct = 50.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(13.852, abs=1e-2)


def test_taupunkt_referenz_minus_2_1c_92prozent() -> None:
    # Arrange: Vorfall-1-naher Frostpunkt (T_a=-2,1 °C, RH=92 % -> T_d = -3,225 °C).
    # Der Entscheidungsbereich des Use-Case liegt um/unter 0 °C -> hier testen.
    air_temp_c = -2.1
    humidity_pct = 92.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(-3.225, abs=1e-2)


def test_taupunkt_referenz_minus_10c_80prozent() -> None:
    # Arrange: tiefer Frost (T_a=-10 °C, RH=80 % -> T_d = -12,797 °C).
    air_temp_c = -10.0
    humidity_pct = 80.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(-12.797, abs=1e-2)


@pytest.mark.parametrize("air_temp_c", [-10.0, -2.1, 0.0, 10.0, 25.0])
def test_taupunkt_immer_kleiner_gleich_lufttemperatur(air_temp_c: float) -> None:
    # Arrange/Act: bei RH < 100 % gilt physikalisch T_d < T_a -- auch im Frost.
    dew_point_c = calculate_dew_point(air_temp_c, 70.0)

    # Assert
    assert dew_point_c < air_temp_c


@pytest.mark.parametrize(
    "invalid_humidity", [0.0, -5.0, 100.1, 150.0, math.nan, math.inf, -math.inf]
)
def test_taupunkt_ungueltige_feuchte_wirft_valueerror(invalid_humidity: float) -> None:
    # Arrange/Act/Assert: RH muss in (0, 100] liegen, sonst ist T_d undefiniert.
    # inf/-inf duerfen nicht still durchrutschen -> klar fangbarer ValueError (NF-01).
    with pytest.raises(ValueError):
        calculate_dew_point(20.0, invalid_humidity)


@pytest.mark.parametrize("invalid_temp", [math.nan, math.inf, -math.inf])
def test_taupunkt_nicht_endliche_temperatur_wirft_valueerror(invalid_temp: float) -> None:
    # Arrange/Act/Assert: NaN/inf-Lufttemperatur darf kein stilles NaN liefern
    # (Fail-safe NF-01) -> klar fangbarer ValueError statt stiller Fehlerquelle.
    with pytest.raises(ValueError):
        calculate_dew_point(invalid_temp, 60.0)


def test_taupunkt_am_magnus_pol_wirft_valueerror() -> None:
    # Arrange/Act/Assert: air_temp_c = -b wuerde durch null teilen -> klarer Fehler
    # statt nacktem ZeroDivisionError (Defense-in-depth; real durch Poller-Range geschuetzt).
    with pytest.raises(ValueError):
        calculate_dew_point(-243.12, 60.0)


@pytest.mark.parametrize("near_pole_temp", [-243.12 - 5e-10, -243.12 + 5e-10])
def test_taupunkt_nahe_magnus_pol_wirft_valueerror(near_pole_temp: float) -> None:
    # Arrange/Act/Assert: Werte, die durch Einlesen/Umrechnung/Rundung minimal neben
    # dem Pol -b landen (z. B. -243,120000000001), duerfen NICHT still durchrutschen.
    # Ein ==0-Vergleich wuerde hier nicht greifen und durch nahezu null teilen ->
    # physikalisch unsinniges Riesen-Ergebnis statt eines fangbaren ValueError (Fail-safe).
    with pytest.raises(ValueError):
        calculate_dew_point(near_pole_temp, 60.0)


@pytest.mark.parametrize("below_pole_temp", [-243.13, -244.0, -250.0, -32768.0])
def test_taupunkt_unterhalb_magnus_pol_wirft_valueerror(below_pole_temp: float) -> None:
    # Arrange/Act/Assert: T_a UNTERHALB des Magnus-Pols (-b) liegt ausserhalb des
    # Definitionsbereichs. Frueher rutschte das still durch -- (b + T_a) wird negativ,
    # die Formel liefert ein physikalisch unsinniges Ergebnis OHNE Fehler. Fail-safe
    # NF-01: muss klar fangbaren ValueError werfen. -32768 simuliert einen korrupten
    # Sensor-Rohwert (Integer-Underflow), der bis hierher durchschlagen koennte.
    with pytest.raises(ValueError):
        calculate_dew_point(below_pole_temp, 70.0)
