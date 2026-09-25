"""
Hardware Step Executor executing SCPI commands over PyVISA or simulated drivers with safety guarantees.
"""

import time
from typing import List, Dict, Optional, Tuple
from hw_test_agent.models.schemas import TestStep, Command, StepOutcome, ActionType
from hw_test_agent.instruments.base import Instrument
from hw_test_agent.agent.validator import SafetyValidator
from hw_test_agent.utils.logging_setup import logger


def execute_step(
    step: TestStep,
    commands: List[Command],
    psu: Instrument,
    scope: Instrument,
    validator: SafetyValidator,
) -> StepOutcome:
    """Executes a single TestStep by sending its SCPI commands to instruments."""
    logger.info(f"Executing Step {step.step_id}: {step.description or step.action}")
    responses: List[str] = []
    sent_commands: List[Command] = []

    # Handle WAIT step without SCPI commands
    if step.action == ActionType.WAIT:
        duration = float(step.params.get("duration_sec", step.params.get("value", 0.1)))
        logger.debug(f"Waiting for {duration} seconds...")
        time.sleep(duration)
        return StepOutcome(step=step, commands_sent=[], responses=[], success=True)

    for cmd in commands:
        # Validate command before touching hardware
        val_res = validator.validate_command(cmd)
        if not val_res.valid:
            err_msg = f"Command '{cmd.scpi}' failed safety validation: {val_res.reasons}"
            logger.error(err_msg)
            return StepOutcome(step=step, commands_sent=sent_commands, responses=responses, success=False, error_message=err_msg)

        sent_commands.append(cmd)
        target_inst = psu if cmd.instrument.lower() == "psu" else scope

        try:
            if cmd.expects_response:
                resp = target_inst.query(cmd.scpi)
                responses.append(resp)
                logger.info(f"[{cmd.instrument.upper()}] QUERY '{cmd.scpi}' -> '{resp}'")
            else:
                target_inst.write(cmd.scpi)
                logger.info(f"[{cmd.instrument.upper()}] WRITE '{cmd.scpi}'")

            # Check instrument error queue after command execution
            err_status = target_inst.check_error()
            if err_status:
                logger.warning(f"[{cmd.instrument.upper()}] Instrument reported error after '{cmd.scpi}': {err_status}")

        except Exception as e:
            err_msg = f"Instrument error while executing '{cmd.scpi}': {e}"
            logger.error(err_msg)
            return StepOutcome(step=step, commands_sent=sent_commands, responses=responses, success=False, error_message=err_msg)

    return StepOutcome(step=step, commands_sent=sent_commands, responses=responses, success=True)


def run_plan(
    plan: List[TestStep],
    commands_map: Dict[int, List[Command]],
    psu: Instrument,
    scope: Instrument,
    validator: SafetyValidator,
) -> List[StepOutcome]:
    """
    Executes an entire test plan sequentially.
    GUARANTEE: The `finally` block ALWAYS disables PSU output safely regardless of errors.
    """
    outcomes: List[StepOutcome] = []

    # Verify order safety before executing
    order_res = validator.check_order(plan)
    if not order_res.valid:
        logger.error(f"Cannot execute test plan: {order_res.reasons}")
        raise ValueError(f"Invalid test plan sequence order: {order_res.reasons}")

    try:
        psu.connect()
        scope.connect()

        for step in plan:
            cmds = commands_map.get(step.step_id, [])
            outcome = execute_step(step, cmds, psu, scope, validator)
            outcomes.append(outcome)

            if not outcome.success:
                logger.error(f"Execution halted at Step {step.step_id} due to failure.")
                break

    finally:
        # ABSOLUTE SAFETY GUARANTEE: Always force PSU output OFF at plan termination!
        logger.info("Executing mandatory safety cleanup: Turning PSU output OFF.")
        try:
            psu.write("OUTP OFF")
        except Exception as e:
            logger.error(f"Failed to turn off PSU output during cleanup: {e}")

    return outcomes
