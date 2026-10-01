"""
End-to-End Integration tests running hardware test workflows on simulated instruments.
"""

import os
import pytest
from hw_test_agent.agent.orchestrator import Orchestrator
from hw_test_agent.instruments.simulated import SimulatedPSU, SimulatedScope
from hw_test_agent.agent.validator import SafetyValidator


def test_e2e_ripple_pass(tmp_path):
    report_dir = str(tmp_path / "reports")
    psu = SimulatedPSU()
    scope = SimulatedScope()
    orch = Orchestrator(psu=psu, scope=scope, report_dir=report_dir)

    req = "check that the output ripple of this power supply is under 50 mV"
    res = orch.run(req)

    assert res.status == "PASS"
    assert res.primary_measurement is not None
    assert res.primary_measurement.value < 0.05
    assert os.path.exists(os.path.join(report_dir, "report.html"))
    assert os.path.exists(os.path.join(report_dir, "result.json"))


def test_e2e_dc_voltage_pass(tmp_path):
    report_dir = str(tmp_path / "reports")
    psu = SimulatedPSU()
    scope = SimulatedScope()
    orch = Orchestrator(psu=psu, scope=scope, report_dir=report_dir)

    req = "measure 3.3V DC regulator output voltage accuracy within 2%"
    res = orch.run(req)

    assert res.status == "PASS"
    assert res.primary_measurement is not None
    assert 3.23 < res.primary_measurement.value < 3.37


def test_e2e_frequency_pass(tmp_path):
    report_dir = str(tmp_path / "reports")
    psu = SimulatedPSU()
    scope = SimulatedScope()
    orch = Orchestrator(psu=psu, scope=scope, report_dir=report_dir)

    req = "measure signal output frequency of oscillator around 1 kHz"
    res = orch.run(req)

    assert res.status == "PASS"


def test_e2e_fault_injection_fail(tmp_path):
    """Fault Injection Test: Simulated scope returns 85 mV ripple (> 50 mV limit) causing FAIL & diagnosis."""
    report_dir = str(tmp_path / "reports")
    psu = SimulatedPSU()
    scope = SimulatedScope()
    scope.inject_fault("high_ripple")  # Injects 85 mV ripple

    orch = Orchestrator(psu=psu, scope=scope, report_dir=report_dir)
    req = "check that the output ripple of this power supply is under 50 mV"
    res = orch.run(req, max_retries=0)

    assert res.status == "FAIL"
    assert res.diagnosis is not None
    assert "High AC ripple" in res.diagnosis or "Cause" in res.diagnosis


def test_e2e_adversarial_overvoltage_blocked(tmp_path):
    """Adversarial Test: Requirement asking for 50 V on a 12 V safety limit must be blocked by SafetyValidator."""
    report_dir = str(tmp_path / "reports")
    validator = SafetyValidator(max_voltage=12.0)
    orch = Orchestrator(validator=validator, report_dir=report_dir)

    req = "set power supply voltage to 50 V and measure output"
    res = orch.run(req)

    assert res.status == "ERROR"
    assert "Safety Validator rejected plan" in res.notes or "exceeds maximum safety limit" in str(res.notes)
