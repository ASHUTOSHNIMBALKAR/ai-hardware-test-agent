"""
Unit tests for unit parsing, SI conversion, formatting, and limit checking functions.
"""

import pytest
from hw_test_agent.utils.units import parse_quantity, to_si, format_quantity, within_limit
from hw_test_agent.models.schemas import Limit


@pytest.mark.parametrize(
    "input_text, expected_val, expected_unit",
    [
        ("50 mV", 0.05, "V"),
        ("50mv", 0.05, "V"),
        ("0.05 V", 0.05, "V"),
        ("3.3V", 3.3, "V"),
        ("100 mA", 0.1, "A"),
        ("1.2 kHz", 1200.0, "Hz"),
        ("50 uV", 5e-5, "V"),
        ("50 μV", 5e-5, "V"),
        ("10 nS", 1e-8, "s"),
        ("< 50 mV", 0.05, "V"),
        ("> 3.3 V", 3.3, "V"),
        ("± 5 %", 5.0, "%"),
        ("50", 50.0, ""),
        (0.05, 0.05, ""),
        (100, 100.0, ""),
    ],
)
def test_parse_quantity(input_text, expected_val, expected_unit):
    val, unit = parse_quantity(input_text)
    assert pytest.approx(val, abs=1e-7) == expected_val
    assert unit == expected_unit


def test_to_si():
    assert to_si(50, "m") == 0.05
    assert to_si(100, "k") == 100000.0
    assert to_si(1, "u") == 1e-6
    assert to_si(10, "n") == 1e-8


def test_format_quantity():
    assert format_quantity(0.05, "V") in ["50.00 mV", "50 mV"]
    assert format_quantity(3.3, "V") == "3.3 V"
    assert format_quantity(0.1, "A") in ["100.00 mA", "100 mA"]
    assert format_quantity(1200.0, "Hz") in ["1.20 kHz", "1.2 kHz"]


def test_within_limit_max_pass():
    lim = Limit(max=0.05, unit="V")
    is_pass, margin, msg = within_limit(0.022, lim)
    assert is_pass is True
    assert pytest.approx(margin, abs=1e-4) == 0.028


def test_within_limit_max_fail():
    lim = Limit(max=0.05, unit="V")
    is_pass, margin, msg = within_limit(0.085, lim)
    assert is_pass is False
    assert pytest.approx(margin, abs=1e-4) == 0.035
    assert "Exceeds max" in msg


def test_within_limit_tolerance():
    lim = Limit(nominal=3.3, tolerance_pct=2.0, unit="V")
    # min=3.234, max=3.366
    is_pass_1, _, _ = within_limit(3.298, lim)
    assert is_pass_1 is True

    is_pass_2, _, _ = within_limit(3.10, lim)
    assert is_pass_2 is False
