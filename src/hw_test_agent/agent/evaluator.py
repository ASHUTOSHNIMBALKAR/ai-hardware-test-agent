"""
Measurement Evaluator parsing raw instrument replies, checking limit criteria, calculating margins and statistics.
"""

import datetime
import math
import re
from typing import List, Dict, Any, Tuple, Optional
from hw_test_agent.models.schemas import TestSpec, Measurement, TestResult, StepOutcome
from hw_test_agent.utils.units import within_limit, format_quantity
from hw_test_agent.utils.logging_setup import logger


def parse_measurement(raw: str, default_unit: str = "V") -> Measurement:
    """Parses raw text returned by instrument query into a Measurement object."""
    clean_raw = raw.strip()
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", clean_raw)
    if not match:
        raise ValueError(f"Could not parse numeric value from raw instrument response: '{raw}'")

    val = float(match.group(0))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return Measurement(value=val, unit=default_unit, timestamp=now_str, raw=clean_raw)


def evaluate(
    spec: TestSpec,
    step_outcomes: List[StepOutcome],
    execution_time: float = 0.0,
) -> TestResult:
    """
    Evaluates step outcomes against TestSpec criteria.
    Extracts measurements, checks limits, computes pass/fail and margins.
    """
    measurements: List[Measurement] = []

    # Extract all measurements returned during step execution
    for outcome in step_outcomes:
        for resp in outcome.responses:
            try:
                m = parse_measurement(resp, default_unit=spec.limit.unit)
                measurements.append(m)
            except Exception as e:
                logger.warning(f"Could not parse measurement from response '{resp}': {e}")

    if not measurements:
        return TestResult(
            spec=spec,
            measurements=[],
            primary_measurement=None,
            status="ERROR",
            margin=None,
            margin_str="No valid measurement captured from instruments",
            notes="Instrument query did not return numeric data.",
            steps_outcomes=step_outcomes,
            execution_time_sec=execution_time,
        )

    # Primary measurement is the latest measurement taken
    primary = measurements[-1]
    is_pass, margin_val, margin_str = within_limit(primary.value, spec.limit)

    status = "PASS" if is_pass else "FAIL"
    val_str = format_quantity(primary.value, spec.limit.unit)
    notes = f"Primary measurement: {val_str}. Evaluation: {status}."

    return TestResult(
        spec=spec,
        measurements=measurements,
        primary_measurement=primary,
        status=status,
        margin=margin_val,
        margin_str=margin_str,
        notes=notes,
        steps_outcomes=step_outcomes,
        execution_time_sec=execution_time,
    )


def compute_statistics(measurements: List[Measurement]) -> Dict[str, float]:
    """Computes mean, std, min, max over repeated measurement samples."""
    if not measurements:
        return {}

    vals = [m.value for m in measurements]
    n = len(vals)
    mean = sum(vals) / n
    variance = sum((x - mean) ** 2 for x in vals) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    return {
        "count": float(n),
        "mean": mean,
        "std": std,
        "min": min(vals),
        "max": max(vals),
    }


def detect_outliers(measurements: List[Measurement], threshold_std: float = 2.0) -> List[Measurement]:
    """Identifies outlier measurements that exceed threshold standard deviations from mean."""
    stats = compute_statistics(measurements)
    if not stats or stats["count"] < 3 or stats["std"] == 0:
        return []

    mean = stats["mean"]
    std = stats["std"]

    outliers = [m for m in measurements if abs(m.value - mean) >= (threshold_std * std - 1e-7)]
    return outliers
