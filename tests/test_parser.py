"""
Unit tests for requirements parsing and normalization.
"""

from hw_test_agent.agent.parser import parse_requirement, normalize_limit
from hw_test_agent.models.schemas import TestSpec, ClarificationNeeded, MeasurementType
from hw_test_agent.llm.client import LLMClient


def test_parse_requirement_ripple():
    llm = LLMClient(fake_mode=True)
    req = "check that the output ripple of this power supply is under 50 mV"
    res = parse_requirement(req, llm_client=llm)
    assert isinstance(res, TestSpec)
    assert res.measurement == MeasurementType.RIPPLE
    assert res.limit.max == 0.05


def test_parse_requirement_dc_voltage():
    llm = LLMClient(fake_mode=True)
    req = "measure 3.3V DC regulator output voltage accuracy"
    res = parse_requirement(req, llm_client=llm)
    assert isinstance(res, TestSpec)
    assert res.measurement == MeasurementType.DC_VOLTAGE


def test_parse_requirement_ambiguous():
    llm = LLMClient(fake_mode=True)
    req = "check power supply"
    res = parse_requirement(req, llm_client=llm)
    assert isinstance(res, ClarificationNeeded)
    assert res.is_ambiguous is True
    assert "Clarifying" in res.question or "specify" in res.question
