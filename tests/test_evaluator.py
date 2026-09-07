"""
Unit tests for evaluator module: measurement parsing, limits, stats, outliers.
"""

import pytest
from hw_test_agent.agent.evaluator import parse_measurement, evaluate, compute_statistics, detect_outliers
from hw_test_agent.models.schemas import TestSpec, Measurement, Limit, StepOutcome, TestStep, ActionType


def test_parse_measurement_float():
    m = parse_measurement("3.29841\n", default_unit="V")
    assert m.value == 3.29841
    assert m.unit == "V"


def test_parse_measurement_scientific():
    m = parse_measurement("2.20000E-02\n", default_unit="V")
    assert pytest.approx(m.value, abs=1e-5) == 0.022


def test_compute_statistics():
    ms = [
        Measurement(value=3.30, unit="V", timestamp=""),
        Measurement(value=3.31, unit="V", timestamp=""),
        Measurement(value=3.29, unit="V", timestamp=""),
    ]
    stats = compute_statistics(ms)
    assert stats["count"] == 3.0
    assert pytest.approx(stats["mean"], abs=1e-3) == 3.30
    assert stats["min"] == 3.29
    assert stats["max"] == 3.31


def test_detect_outliers():
    ms = [
        Measurement(value=3.30, unit="V", timestamp=""),
        Measurement(value=3.30, unit="V", timestamp=""),
        Measurement(value=3.30, unit="V", timestamp=""),
        Measurement(value=3.31, unit="V", timestamp=""),
        Measurement(value=5.50, unit="V", timestamp=""),  # Clear outlier
    ]
    outliers = detect_outliers(ms, threshold_std=1.5)
    assert len(outliers) == 1
    assert outliers[0].value == 5.50
