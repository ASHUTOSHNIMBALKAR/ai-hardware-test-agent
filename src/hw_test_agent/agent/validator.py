"""
Safety Validator enforcing command whitelisting, voltage/current bounds, and test step sequence order.
"""

import re
from typing import List, Dict, Optional
from hw_test_agent.models.schemas import Command, TestStep, ActionType, ValidationResult
from hw_test_agent.utils.logging_setup import logger

# Default laboratory hardware safety limits
DEFAULT_MAX_VOLTAGE = 12.0  # Volts DC
DEFAULT_MAX_CURRENT = 2.0   # Amperes DC

# Allowed SCPI verbs & prefixes
ALLOWED_SCPI_PREFIXES = [
    "VOLT", "CURR", "OUTP", "MEAS", "CHAN", "TIM",
    "*IDN?", "*RST", "SYST:ERR?", "*ESR?"
]

DANGEROUS_COMMAND_KEYWORDS = [
    "CAL:", "CALIBRATE", "FLASH", "ERASE", "FORMAT", "DIAG:", "MEM:WRITE", "PROTECT:CLEAR"
]


class SafetyValidator:
    """Hardware Safety Validator ensuring commands cannot damage lab equipment or DUT."""

    def __init__(self, max_voltage: float = DEFAULT_MAX_VOLTAGE, max_current: float = DEFAULT_MAX_CURRENT):
        self.max_voltage = max_voltage
        self.max_current = max_current

    def validate_command(self, cmd: Command) -> ValidationResult:
        """Validates a single SCPI command string against safety rules."""
        scpi = cmd.scpi.strip().upper()
        reasons = []
        requires_confirmation = False

        # 1. Check for dangerous hardware management SCPI keywords
        for dangerous in DANGEROUS_COMMAND_KEYWORDS:
            if dangerous in scpi:
                reasons.append(f"Rejected dangerous keyword '{dangerous}' in command '{scpi}'")
                return ValidationResult(valid=False, reasons=reasons)

        # 2. Whitelist command prefix check
        is_whitelisted = any(scpi.startswith(prefix) for prefix in ALLOWED_SCPI_PREFIXES)
        if not is_whitelisted:
            reasons.append(f"Command '{scpi}' is not in the allowed SCPI whitelist database")

        # 3. Voltage parameter bounds check
        if scpi.startswith("VOLT"):
            match = re.search(r"VOLT\s+(-?\d+(?:\.\d+)?)", scpi)
            if match:
                val = float(match.group(1))
                if val > self.max_voltage:
                    reasons.append(f"Requested voltage {val}V exceeds maximum safety limit of {self.max_voltage}V")
                elif val < 0:
                    reasons.append(f"Negative voltage {val}V not supported on single-rail supply")
                elif val > 10.0:
                    requires_confirmation = True

        # 4. Current parameter bounds check
        if scpi.startswith("CURR"):
            match = re.search(r"CURR\s+(-?\d+(?:\.\d+)?)", scpi)
            if match:
                val = float(match.group(1))
                if val > self.max_current:
                    reasons.append(f"Requested current limit {val}A exceeds maximum safety limit of {self.max_current}A")
                elif val <= 0:
                    reasons.append(f"Invalid current limit {val}A must be strictly positive")

        valid = len(reasons) == 0
        if not valid:
            logger.warning(f"Safety Validation Failure: {reasons}")

        return ValidationResult(valid=valid, reasons=reasons, requires_confirmation=requires_confirmation)

    def check_order(self, steps: List[TestStep]) -> ValidationResult:
        """Enforces safe test execution order rules across plan steps."""
        reasons = []

        has_curr_limit = False
        enable_output_index = -1
        disable_output_present = False

        for idx, step in enumerate(steps):
            if step.action == ActionType.SET_CURRENT_LIMIT or "current_limit" in step.params:
                has_curr_limit = True

            if step.action == ActionType.ENABLE_OUTPUT:
                enable_output_index = idx
                if not has_curr_limit:
                    reasons.append(
                        f"Safety Violation at step {step.step_id}: ENABLE_OUTPUT attempted before configuring a current limit."
                    )

            if step.action == ActionType.DISABLE_OUTPUT:
                disable_output_present = True

        if not disable_output_present:
            reasons.append("Safety Violation: Test plan is missing required final DISABLE_OUTPUT cleanup step.")

        valid = len(reasons) == 0
        return ValidationResult(valid=valid, reasons=reasons)

    def dry_run(self, steps: List[TestStep], generated_commands: List[Command]) -> ValidationResult:
        """Performs a comprehensive dry run of steps and commands without executing on hardware."""
        reasons = []
        requires_conf = False

        order_res = self.check_order(steps)
        if not order_res.valid:
            reasons.extend(order_res.reasons)

        for cmd in generated_commands:
            cmd_res = self.validate_command(cmd)
            if not cmd_res.valid:
                reasons.extend(cmd_res.reasons)
            if cmd_res.requires_confirmation:
                requires_conf = True

        valid = len(reasons) == 0
        return ValidationResult(valid=valid, reasons=reasons, requires_confirmation=requires_conf)
