"""
Requirement Parser converting English test text into a normalized TestSpec or ClarificationNeeded request.
"""

from typing import Union, Optional
from hw_test_agent.models.schemas import TestSpec, ClarificationNeeded, MeasurementType, Limit
from hw_test_agent.llm.client import LLMClient
from hw_test_agent.llm.prompts import PARSER_PROMPT
from hw_test_agent.utils.units import parse_quantity
from hw_test_agent.utils.logging_setup import logger


def parse_requirement(text: str, llm_client: Optional[LLMClient] = None) -> Union[TestSpec, ClarificationNeeded]:
    """
    Parses plain English text requirement into a structured TestSpec or ClarificationNeeded.
    """
    if llm_client is None:
        llm_client = LLMClient()

    logger.info(f"Parsing requirement text: '{text}'")

    # Fast heuristic ambiguity check before calling LLM
    text_lower = text.lower().strip()
    if text_lower in ["check power supply", "test circuit", "run test", "measure dut"]:
        return ClarificationNeeded(
            is_ambiguous=True,
            question="Please specify what parameter to measure (e.g. DC voltage, ripple, frequency) and the pass/fail limit.",
            missing_fields=["measurement", "limit"],
        )

    # Call LLM client to request structured TestSpec
    res = llm_client.complete_json(
        system_prompt=PARSER_PROMPT,
        user_prompt=f"Requirement: {text}",
        schema_cls=TestSpec,
    )

    if isinstance(res, ClarificationNeeded):
        return res

    if isinstance(res, TestSpec):
        # Post-process: normalize limit units and values to SI
        res = normalize_limit(res)
        return res

    return ClarificationNeeded(
        is_ambiguous=True,
        question="Could not understand the test requirement. Please rephrase with target measurement and limit.",
        missing_fields=["specification"],
    )


def normalize_limit(spec: TestSpec) -> TestSpec:
    """Normalizes spec limit values and units to SI standard (e.g. 50 mV -> 0.05 V)."""
    lim = spec.limit

    if lim.max is not None and isinstance(lim.max, str):
        val, unit = parse_quantity(str(lim.max))
        lim.max = val
        lim.unit = unit or lim.unit

    if lim.min is not None and isinstance(lim.min, str):
        val, unit = parse_quantity(str(lim.min))
        lim.min = val
        lim.unit = unit or lim.unit

    if lim.nominal is not None and isinstance(lim.nominal, str):
        val, unit = parse_quantity(str(lim.nominal))
        lim.nominal = val
        lim.unit = unit or lim.unit

    # If unit contains prefix e.g. 'mV' or 'kHz', adjust max/min/nominal
    if lim.unit and lim.unit not in ["V", "A", "Hz", "s", "Ohm", "Ω", "%"]:
        if lim.unit.endswith("V") or lim.unit.endswith("A") or lim.unit.endswith("Hz"):
            if lim.max is not None and lim.max > 1.0 and ("mV" in lim.unit or "mA" in lim.unit):
                lim.max = lim.max / 1000.0
            if lim.min is not None and lim.min > 1.0 and ("mV" in lim.unit or "mA" in lim.unit):
                lim.min = lim.min / 1000.0

    return spec
