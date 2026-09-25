"""
Test Planner generating deterministic safe step sequences for hardware measurement specs.
"""

from typing import List, Optional
from hw_test_agent.models.schemas import TestSpec, TestStep, ActionType, MeasurementType
from hw_test_agent.llm.client import LLMClient
from hw_test_agent.utils.logging_setup import logger


def plan(spec: TestSpec, llm_client: Optional[LLMClient] = None) -> List[TestStep]:
    """Generates ordered list of TestSteps from a TestSpec using standard recipes or LLM fallback."""
    logger.info(f"Planning step sequence for spec: {spec.name} ({spec.measurement})")

    steps = _load_recipe_template(spec)
    if not steps:
        logger.info(f"No built-in template for '{spec.measurement}'. Falling back to LLM step planner.")
        steps = _llm_plan(spec, llm_client or LLMClient())

    steps = order_steps(steps)
    return steps


def _load_recipe_template(spec: TestSpec) -> List[TestStep]:
    """Standard known-good recipes matching measurement types."""
    meas = spec.measurement
    voltage = spec.condition.get("input_voltage", spec.condition.get("voltage", 3.3))
    current_limit = spec.condition.get("current_limit", 1.0)

    if meas == MeasurementType.DC_VOLTAGE:
        return [
            TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": current_limit}, description="Set current limit"),
            TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": voltage}, description=f"Set PSU voltage to {voltage}V"),
            TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT, description="Turn on power supply output"),
            TestStep(step_id=4, action=ActionType.WAIT, params={"duration_sec": 0.1}, description="Wait for rail settling"),
            TestStep(step_id=5, action=ActionType.MEASURE, params={"target": "voltage", "instrument": "psu"}, description="Measure DC output voltage"),
            TestStep(step_id=6, action=ActionType.DISABLE_OUTPUT, description="Turn off power supply output"),
        ]

    elif meas == MeasurementType.RIPPLE:
        return [
            TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": current_limit}, description="Set current limit"),
            TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": voltage}, description=f"Set PSU voltage to {voltage}V"),
            TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT, description="Turn on power supply output"),
            TestStep(step_id=4, action=ActionType.CONFIGURE_SCOPE, params={"coupling": "AC", "vertical_scale": 0.05, "timebase": 1e-3}, description="Configure oscilloscope channel 1 AC coupled"),
            TestStep(step_id=5, action=ActionType.WAIT, params={"duration_sec": 0.1}, description="Wait for AC coupling settling"),
            TestStep(step_id=6, action=ActionType.MEASURE, params={"target": "vpp", "instrument": "scope"}, description="Measure peak-to-peak AC ripple voltage (Vpp)"),
            TestStep(step_id=7, action=ActionType.DISABLE_OUTPUT, description="Turn off power supply output"),
        ]

    elif meas == MeasurementType.FREQUENCY:
        return [
            TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": current_limit}, description="Set current limit"),
            TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": voltage}, description=f"Set PSU voltage to {voltage}V"),
            TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT, description="Turn on power supply output"),
            TestStep(step_id=4, action=ActionType.CONFIGURE_SCOPE, params={"coupling": "DC", "timebase": 1e-3}, description="Configure oscilloscope channel 1 DC coupled"),
            TestStep(step_id=5, action=ActionType.MEASURE, params={"target": "freq", "instrument": "scope"}, description="Measure frequency"),
            TestStep(step_id=6, action=ActionType.DISABLE_OUTPUT, description="Turn off power supply output"),
        ]

    elif meas == MeasurementType.CURRENT:
        return [
            TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": current_limit}, description="Set current limit"),
            TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": voltage}, description=f"Set PSU voltage to {voltage}V"),
            TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT, description="Turn on power supply output"),
            TestStep(step_id=4, action=ActionType.WAIT, params={"duration_sec": 0.1}, description="Wait for current stabilization"),
            TestStep(step_id=5, action=ActionType.MEASURE, params={"target": "current", "instrument": "psu"}, description="Measure supply current draw"),
            TestStep(step_id=6, action=ActionType.DISABLE_OUTPUT, description="Turn off power supply output"),
        ]

    return []


def _llm_plan(spec: TestSpec, llm_client: LLMClient) -> List[TestStep]:
    """Fallback LLM planner when spec does not match pre-packaged recipes."""
    # Deterministic fallback list if offline
    voltage = spec.condition.get("input_voltage", 3.3)
    return [
        TestStep(step_id=1, action=ActionType.SET_CURRENT_LIMIT, params={"value": 1.0}),
        TestStep(step_id=2, action=ActionType.SET_SUPPLY, params={"value": voltage}),
        TestStep(step_id=3, action=ActionType.ENABLE_OUTPUT),
        TestStep(step_id=4, action=ActionType.MEASURE, params={"target": spec.measurement.value, "instrument": "psu"}),
        TestStep(step_id=5, action=ActionType.DISABLE_OUTPUT),
    ]


def order_steps(steps: List[TestStep]) -> List[TestStep]:
    """
    Ensures safe step ordering:
    1. SET_CURRENT_LIMIT and SET_SUPPLY must come before ENABLE_OUTPUT.
    2. DISABLE_OUTPUT must ALWAYS be the final step.
    """
    if not steps:
        return steps

    # Remove existing disable_output steps if any to re-append at exact end
    filtered_steps = [s for s in steps if s.action != ActionType.DISABLE_OUTPUT]

    # Re-index step IDs
    for idx, s in enumerate(filtered_steps, start=1):
        s.step_id = idx

    # Append guaranteed disable output cleanup step
    disable_step = TestStep(
        step_id=len(filtered_steps) + 1,
        action=ActionType.DISABLE_OUTPUT,
        description="Safety Cleanup: Turn off power supply output",
    )
    filtered_steps.append(disable_step)

    return filtered_steps
