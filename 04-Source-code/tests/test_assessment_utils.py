"""Tests fuer die Taupunktberechnung (Magnus-Formel, DTB-32).

Referenzwerte und Magnus-Parameter (a=17,62; b=243,12 °C) stammen aus
Schwellenwerte.md §1 im Arbeitsrepo. Es werden nur bekannte Referenzwerte
geprueft, nichts dazuerfunden.
"""

import pytest

from src.assessment.utils import calculate_dew_point


def test_taupunkt_gleich_lufttemperatur_bei_saettigung_20c() -> None:
    # Arrange: bei 100 % Luftfeuchte ist der Taupunkt gleich der Lufttemperatur.
    air_temp_c = 20.0
    humidity_pct = 100.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
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
    # Arrange: Ticket-Referenz DTB-32 (T_a=20 °C, RH=60 % -> T_d ~= 11,9 °C).
    air_temp_c = 20.0
    humidity_pct = 60.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(11.9, abs=0.2)


def test_taupunkt_referenz_25c_50prozent() -> None:
    # Arrange: meteorologischer Standardwert (T_a=25 °C, RH=50 % -> T_d ~= 13,9 °C).
    air_temp_c = 25.0
    humidity_pct = 50.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c == pytest.approx(13.9, abs=0.2)


def test_taupunkt_immer_kleiner_gleich_lufttemperatur() -> None:
    # Arrange: physikalisch gilt T_d <= T_a (Gleichheit nur bei 100 % RH).
    air_temp_c = 10.0
    humidity_pct = 70.0

    # Act
    dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)

    # Assert
    assert dew_point_c < air_temp_c


@pytest.mark.parametrize("invalid_humidity", [0.0, -5.0, 100.1, 150.0])
def test_taupunkt_ungueltige_feuchte_wirft_valueerror(invalid_humidity: float) -> None:
    # Arrange/Act/Assert: RH muss in (0, 100] liegen, sonst ist T_d undefiniert.
    with pytest.raises(ValueError):
        calculate_dew_point(20.0, invalid_humidity)
