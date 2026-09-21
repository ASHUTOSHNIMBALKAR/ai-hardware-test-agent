"""
Unit tests for SafetyValidator bounds checking, whitelisting, and order rules.
"""

from hw_test_agent.agent.validator import SafetyValidator
from hw_test_agent.models.schemas import Command, TestStep, ActionType


def test_validator_safe_voltage():
    v = SafetyValidator(max_voltage=12.0)
    cmd = Command(instrument="psu", scpi="VOLT 5.0")
    res = v.validate_command(cmd)
    assert res.valid is True


def test_validator_overvoltage_blocked():
    v = SafetyValidator(max_voltage=12.0)
    cmd = Command(instrument="psu", scpi="VOLT 50.0")
    res = v.validate_command(cmd)
    assert res.valid is False
    assert any("exceeds maximum safety limit" in r for r in res.reasons)


def test_validator_overcurrent_blocked():
    v = SafetyValidator(max_current=2.0)
    cmd = Command(instrument="psu", scpi="CURR 5.0")
    res = v.validate_command(cmd)
    assert res.valid is False
    assert any("exceeds maximum safety limit" in r for r in res.reasons)


def test_validator_dangerous_keyword_blocked():
    v = SafetyValidator()
    cmd = Command(instrument="psu", scpi="CAL:ZERO:ALL")
    res = v.validate_command(cmd)
    assert res.valid is False
    assert any("Rejected dangerous keyword" in r for r in res.reasons)


def test_validator_unwhitelisted_scpi_blocked():
    v = SafetyValidator()
    cmd = Command(instrument="psu", scpi="FOOBAR:BAZ 123")
    res = v.validate_command(cmd)
    assert res.valid is False
    assert any("not in the allowed SCPI whitelist" in r for r in res.reasons)


def test_validator_step_order_valid():
    v = SafetyValidator()
    steps = [
        TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": 1.0}),
        TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": 3.3}),
        TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT),
        TestStep(step_id=4, action=ActionType.DISABLE_OUTPUT),
    ]
    res = v.check_order(steps)
    assert res.valid is True


def test_validator_step_order_missing_current_limit():
    v = SafetyValidator()
    steps = [
        TestStep(step_id=1, action=ActionType.SET_SUPPLY, params={"value": 3.3}),
        TestStep(step_id=2, action=ActionType.ENABLE_OUTPUT),
        TestStep(step_id=3, action=ActionType.DISABLE_OUTPUT),
    ]
    res = v.check_order(steps)
    assert res.valid is False
    assert any("before configuring a current limit" in r for r in res.reasons)


def test_validator_step_order_missing_disable_output():
    v = SafetyValidator()
    steps = [
        TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": 1.0}),
        TestStep(step_id=2, action=ActionType.ENABLE_OUTPUT),
    ]
    res = v.check_order(steps)
    assert res.valid is False
    assert any("missing required final DISABLE_OUTPUT" in r for r in res.reasons)
