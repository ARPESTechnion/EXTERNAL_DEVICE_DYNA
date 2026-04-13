"""Tests for v3.core.calibration."""

import math
import pytest

from v3.core.calibration import CalibrationConfig


class TestCalibrationDefaults:
    """Test default calibration values match the V2 system."""

    def test_default_ga_per_coil(self):
        cal = CalibrationConfig()
        assert cal.ga_per_coil == 341.71

    def test_default_num_coils(self):
        cal = CalibrationConfig()
        assert cal.num_coils == 2

    def test_ga_total_computed(self):
        cal = CalibrationConfig()
        assert cal.ga_total == pytest.approx(341.71)

    def test_default_hall_v2gauss(self):
        cal = CalibrationConfig()
        assert cal.hall_v2gauss == 1.0

    def test_default_hall_offset(self):
        cal = CalibrationConfig()
        assert cal.hall_offset_v == 0.0


class TestHelmholtzConversions:
    def test_current_to_field(self):
        cal = CalibrationConfig()
        # 1 A total → 341.71 G
        assert cal.current_to_field(1.0) == pytest.approx(341.71)

    def test_field_to_current(self):
        cal = CalibrationConfig()
        # 341.71 G → 1 A
        assert cal.field_to_current(341.71) == pytest.approx(1.0)

    def test_roundtrip(self):
        cal = CalibrationConfig()
        for current in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
            field = cal.current_to_field(current)
            back = cal.field_to_current(field)
            assert back == pytest.approx(current)

    def test_zero_field(self):
        cal = CalibrationConfig()
        assert cal.current_to_field(0.0) == 0.0
        assert cal.field_to_current(0.0) == 0.0

    def test_negative_field(self):
        cal = CalibrationConfig()
        assert cal.current_to_field(-1.0) == pytest.approx(-341.71)
        assert cal.field_to_current(-341.71) == pytest.approx(-1.0)

    def test_coil_current(self):
        cal = CalibrationConfig()
        # 3 A total → 1.5 A per coil
        assert cal.coil_current(3.0) == pytest.approx(1.5)

    def test_custom_calibration(self):
        cal = CalibrationConfig(ga_per_coil=400.0, num_coils=3)
        assert cal.ga_total == pytest.approx(400.0)
        assert cal.current_to_field(1.0) == pytest.approx(400.0)
        assert cal.field_to_current(400.0) == pytest.approx(1.0)

    def test_zero_ga_total_raises(self):
        cal = CalibrationConfig(ga_per_coil=0.0, num_coils=2)
        with pytest.raises(ZeroDivisionError):
            cal.field_to_current(100.0)


class TestHallConversions:
    def test_voltage_to_field_no_offset(self):
        cal = CalibrationConfig(hall_v2gauss=10.0, hall_offset_v=0.0)
        assert cal.hall_voltage_to_field(0.5) == pytest.approx(5.0)

    def test_voltage_to_field_with_offset(self):
        cal = CalibrationConfig(hall_v2gauss=10.0, hall_offset_v=0.1)
        assert cal.hall_voltage_to_field(0.5) == pytest.approx(4.0)

    def test_field_error(self):
        cal = CalibrationConfig(hall_v2gauss=10.0)
        assert cal.hall_field_error(0.01) == pytest.approx(0.1)

    def test_field_error_always_positive(self):
        cal = CalibrationConfig(hall_v2gauss=-10.0)
        assert cal.hall_field_error(0.01) == pytest.approx(0.1)
