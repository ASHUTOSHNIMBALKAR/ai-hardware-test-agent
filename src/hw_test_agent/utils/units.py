"""
Unit parsing, conversion to SI units, formatting, and limit checking utilities.
"""

import re
from typing import Tuple, Optional
from hw_test_agent.models.schemas import Limit

PREFIX_FACTORS = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "μ": 1e-6,
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
}

KNOWN_UNITS = ["V", "A", "Hz", "s", "Ohm", "Ω", "W", "%"]


def to_si(value: float, prefix: str) -> float:
    """Converts a value with metric prefix to SI base unit value."""
    factor = PREFIX_FACTORS.get(prefix, 1.0)
    return value * factor


def parse_quantity(text: str) -> Tuple[float, str]:
    """
    Parses strings like '50 mV', '50mv', '0.05 V', '100 mA', '1.2 kHz', '< 50 mV'
    into a tuple of (value_in_si, base_unit).
    """
    if isinstance(text, (int, float)):
        return float(text), ""

    s = str(text).strip()
    # Strip comparison operators like <, >, <=, >=, ==, ±
    s = re.sub(r"^[<>=±~]+\s*", "", s)

    # Match numeric part and rest
    pattern = r"^(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-ZμΩ%]*)$"
    match = re.match(pattern, s)
    if not match:
        # Fallback regex search for embedded numbers
        match_num = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s)
        if match_num:
            val = float(match_num.group(0))
            rest = s[match_num.end():].strip()
            return _extract_prefix_unit(val, rest)
        raise ValueError(f"Cannot parse quantity from text: '{text}'")

    val_str, unit_part = match.groups()
    val = float(val_str)
    return _extract_prefix_unit(val, unit_part)


def _extract_prefix_unit(val: float, unit_part: str) -> Tuple[float, str]:
    if not unit_part:
        return val, ""

    unit_part = unit_part.strip()
    
    # Standard unit casing mapping
    unit_map = {"V": "V", "v": "V", "A": "A", "a": "A", "HZ": "Hz", "Hz": "Hz", "hz": "Hz", "S": "s", "s": "s", "W": "W", "w": "W", "%": "%", "OHM": "Ohm", "ohm": "Ohm", "Ω": "Ω"}

    if unit_part in unit_map:
        return val, unit_map[unit_part]

    # Check multi-letter base units: 'Hz', 'Vpp', 'V', 'A', 's'
    base_units = [("hz", "Hz"), ("vpp", "Vpp"), ("v", "V"), ("a", "A"), ("s", "s"), ("w", "W")]
    unit_lower = unit_part.lower()

    for bu_lower, bu_norm in base_units:
        if unit_lower.endswith(bu_lower):
            prefix_part = unit_part[:-len(bu_lower)]
            prefix = prefix_part if prefix_part in PREFIX_FACTORS else ""
            si_val = to_si(val, prefix)
            return si_val, bu_norm

    # First char as prefix, rest as unit
    prefix_char = unit_part[0]
    if prefix_char in PREFIX_FACTORS:
        si_val = to_si(val, prefix_char)
        base_unit = unit_part[1:]
        base_unit = unit_map.get(base_unit, unit_map.get(base_unit.lower(), base_unit))
        return si_val, base_unit

    return val, unit_part


def format_quantity(value: float, unit: str) -> str:
    """Formats a value in SI base units into human-readable metric string (e.g. 0.05 V -> '50 mV')."""
    if value == 0:
        return f"0 {unit}".strip()

    abs_val = abs(value)

    if abs_val >= 1e9:
        return f"{value / 1e9:.2f} G{unit}".strip()
    elif abs_val >= 1e6:
        return f"{value / 1e6:.2f} M{unit}".strip()
    elif abs_val >= 1e3:
        return f"{value / 1e3:.2f} k{unit}".strip()
    elif abs_val >= 1.0 or unit == "%":
        return f"{value:.3g} {unit}".strip()
    elif abs_val >= 1e-3:
        return f"{value * 1e3:.2f} m{unit}".strip()
    elif abs_val >= 1e-6:
        return f"{value * 1e6:.2f} u{unit}".strip()
    elif abs_val >= 1e-9:
        return f"{value * 1e9:.2f} n{unit}".strip()
    else:
        return f"{value * 1e12:.2f} p{unit}".strip()


def within_limit(value: float, limit: Limit) -> Tuple[bool, Optional[float], str]:
    """
    Evaluates if value is within specified Limit object.
    Returns (is_pass, margin_value, formatted_margin_str).
    """
    min_bound = limit.min
    max_bound = limit.max

    if limit.nominal is not None and limit.tolerance_pct is not None:
        tol = abs(limit.nominal * (limit.tolerance_pct / 100.0))
        min_bound = limit.nominal - tol if min_bound is None else min_bound
        max_bound = limit.nominal + tol if max_bound is None else max_bound

    is_pass = True
    margin_val = None
    margin_str = ""

    if min_bound is not None and max_bound is not None:
        if value < min_bound:
            is_pass = False
            margin_val = value - min_bound
            margin_str = f"Below min by {format_quantity(abs(margin_val), limit.unit)}"
        elif value > max_bound:
            is_pass = False
            margin_val = value - max_bound
            margin_str = f"Exceeds max by {format_quantity(margin_val, limit.unit)}"
        else:
            # Pass: calculate closest distance to bounds
            dist_min = value - min_bound
            dist_max = max_bound - value
            margin_val = min(dist_min, dist_max)
            margin_str = f"Within limits (margin: {format_quantity(margin_val, limit.unit)})"

    elif max_bound is not None:
        if value > max_bound:
            is_pass = False
            margin_val = value - max_bound
            margin_str = f"Exceeds max by {format_quantity(margin_val, limit.unit)}"
        else:
            margin_val = max_bound - value
            margin_str = f"Under max limit by {format_quantity(margin_val, limit.unit)}"

    elif min_bound is not None:
        if value < min_bound:
            is_pass = False
            margin_val = value - min_bound
            margin_str = f"Below min limit by {format_quantity(abs(margin_val), limit.unit)}"
        else:
            margin_val = value - min_bound
            margin_str = f"Above min limit by {format_quantity(margin_val, limit.unit)}"

    return is_pass, margin_val, margin_str
