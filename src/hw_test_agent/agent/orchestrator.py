"""
Test Orchestrator controlling full pipeline: Parser -> Planner -> Generator -> Validator -> Executor -> Evaluator -> Retry/Diagnosis -> Reporter.
"""

import time
from typing import Optional, Tuple
from hw_test_agent.models.schemas import TestSpec, TestResult, ClarificationNeeded, Command, TestStep
from hw_test_agent.agent.parser import parse_requirement
from hw_test_agent.agent.planner import plan
from hw_test_agent.agent.generator import generate_commands
from hw_test_agent.agent.validator import SafetyValidator
from hw_test_agent.agent.executor import run_plan
from hw_test_agent.agent.evaluator import evaluate
from hw_test_agent.agent.reporter import build_report, export_json
from hw_test_agent.instruments.base import Instrument
from hw_test_agent.instruments.simulated import SimulatedPSU, SimulatedScope
from hw_test_agent.llm.client import LLMClient
from hw_test_agent.llm.prompts import DIAGNOSE_PROMPT
from hw_test_agent.utils.logging_setup import logger


class Orchestrator:
    """End-to-End Autonomous Hardware Test Orchestrator."""

    def __init__(
        self,
        psu: Optional[Instrument] = None,
        scope: Optional[Instrument] = None,
        validator: Optional[SafetyValidator] = None,
        llm_client: Optional[LLMClient] = None,
        report_dir: str = "reports",
    ):
        self.psu = psu or SimulatedPSU()
        self.scope = scope or SimulatedScope()
        if isinstance(self.scope, SimulatedScope) and isinstance(self.psu, SimulatedPSU):
            self.scope.psu_ref = self.psu

        self.validator = validator or SafetyValidator()
        self.llm_client = llm_client or LLMClient()
        self.report_dir = report_dir

    def run(
        self,
        requirement: str,
        max_retries: int = 2,
        dry_run_only: bool = False,
    ) -> TestResult:
        """Executes full automated test workflow from plain English requirement to HTML report."""
        start_time = time.time()
        logger.info(f"=== Starting Hardware Test Execution for: '{requirement}' ===")

        # 1. Parse requirement
        spec_or_clarify = parse_requirement(requirement, self.llm_client)

        if isinstance(spec_or_clarify, ClarificationNeeded):
            logger.warning(f"Requirement is ambiguous: {spec_or_clarify.question}")
            dummy_spec = TestSpec(
                name="Ambiguous Test Requirement",
                measurement="dc_voltage",
                limit={"unit": "V"},
            )
            return TestResult(
                spec=dummy_spec,
                status="ERROR",
                margin_str="Ambiguous input",
                notes=f"Clarification Required: {spec_or_clarify.question}",
            )

        spec: TestSpec = spec_or_clarify
        logger.info(f"Parsed TestSpec: {spec.name} (Measurement: {spec.measurement})")

        # 2. Plan test steps
        steps = plan(spec, self.llm_client)

        # 3. Generate SCPI commands map
        commands_map = {step.step_id: generate_commands(step) for step in steps}
        all_commands = [cmd for step_cmds in commands_map.values() for cmd in step_cmds]

        # 4. Perform Safety Validation & Dry Run
        dry_run_res = self.validator.dry_run(steps, all_commands)
        if not dry_run_res.valid:
            logger.error(f"Dry Run Safety Check Failed: {dry_run_res.reasons}")
            return TestResult(
                spec=spec,
                status="ERROR",
                margin_str="Safety Validation Failed",
                notes=f"Safety Validator rejected plan: {dry_run_res.reasons}",
            )

        if dry_run_only:
            logger.info("Dry run completed successfully. Halting execution as requested.")
            return TestResult(
                spec=spec,
                status="PASS",
                margin_str="Dry run passed safety checks",
                notes="Dry run mode only - no hardware commands executed.",
            )

        # 5. Execute Plan with Retry Loop on Measurement Failures
        attempts = 0
        final_result = None

        while attempts <= max_retries:
            attempts += 1
            logger.info(f"Test Execution Attempt {attempts}/{max_retries + 1}")

            outcomes = run_plan(steps, commands_map, self.psu, self.scope, self.validator)
            exec_time = time.time() - start_time
            result = evaluate(spec, outcomes, execution_time=exec_time)

            if result.status == "PASS" or attempts > max_retries:
                final_result = result
                break

            logger.warning(f"Attempt {attempts} resulted in status '{result.status}'. Retrying...")
            time.sleep(0.2)

        # 6. Failure Root Cause Diagnosis via LLM if test failed
        if final_result and final_result.status == "FAIL":
            final_result.diagnosis = self._diagnose_failure(final_result)

        # 7. Generate HTML & JSON Reports
        report_html = f"{self.report_dir}/report.html"
        report_json = f"{self.report_dir}/result.json"
        build_report(final_result, report_html)
        export_json(final_result, report_json)

        logger.info(f"=== Test Completed with Status: {final_result.status} ===")
        return final_result

    def _diagnose_failure(self, result: TestResult) -> str:
        """Invokes LLM root cause failure analysis for failed hardware tests."""
        logger.info("Invoking failure diagnosis engine...")
        meas_val = result.primary_measurement.value if result.primary_measurement else "N/A"
        prompt = (
            f"Hardware Test '{result.spec.name}' FAILED.\n"
            f"Measurement Type: {result.spec.measurement}\n"
            f"Measured Value: {meas_val} {result.spec.limit.unit}\n"
            f"Target Limit: Max={result.spec.limit.max}, Min={result.spec.limit.min}\n"
            f"Margin Info: {result.margin_str}\n"
        )

        try:
            if self.llm_client.fake_mode:
                if result.spec.measurement == "ripple":
                    return (
                        "Probable Cause: High AC ripple detected. Check output decoupling capacitor ESR, "
                        "reduce oscilloscope probe ground loop area, or verify load current transient."
                    )
                else:
                    return (
                        "Probable Cause: Voltage rail regulation out of tolerance. Check feedback resistor tolerances, "
                        "input voltage headroom, or thermal throttling."
                    )

            res = self.llm_client.complete_json(
                system_prompt=DIAGNOSE_PROMPT,
                user_prompt=prompt,
                schema_cls=dict,  # type: ignore
            )
            return str(res)
        except Exception as e:
            logger.error(f"Diagnosis generation failed: {e}")
            return "Failure diagnosis unavailable."
