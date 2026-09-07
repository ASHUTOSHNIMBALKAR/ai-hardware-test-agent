"""
Pydantic data models and schemas for hardware test agent.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MeasurementType(str, Enum):
    DC_VOLTAGE = "dc_voltage"
    RIPPLE = "ripple"
    FREQUENCY = "frequency"
    CURRENT = "current"
    RISE_TIME = "rise_time"
    LINE_REGULATION = "line_regulation"
    LOAD_REGULATION = "load_regulation"


class ActionType(str, Enum):
    SET_SUPPLY = "set_supply"
    SET_CURRENT_LIMIT = "set_current_limit"
    ENABLE_OUTPUT = "enable_output"
    CONFIGURE_SCOPE = "configure_scope"
    MEASURE = "measure"
    WAIT = "wait"
    DISABLE_OUTPUT = "disable_output"


class Limit(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    nominal: Optional[float] = None
    tolerance_pct: Optional[float] = None
    unit: str = ""


class TestSpec(BaseModel):
    __test__ = False
    name: str = Field(description="Name or title of the test")
    dut: str = Field(default="Generic DUT", description="Device Under Test identifier")
    measurement: MeasurementType = Field(description="Type of electronics measurement")
    condition: Dict[str, Any] = Field(default_factory=dict, description="Test operating conditions e.g. input voltage, load")
    limit: Limit = Field(description="Pass/Fail limit constraints")


class ClarificationNeeded(BaseModel):
    is_ambiguous: bool = True
    question: str = Field(description="Clarification question to present to the user")
    missing_fields: List[str] = Field(default_factory=list, description="Fields that could not be inferred")


class TestStep(BaseModel):
    __test__ = False
    step_id: int
    action: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class Command(BaseModel):
    instrument: str = Field(description="'psu' or 'scope'")
    scpi: str = Field(description="Raw SCPI command string")
    expects_response: bool = False
    description: str = ""


class ValidationResult(BaseModel):
    valid: bool
    reasons: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class Measurement(BaseModel):
    value: float
    unit: str
    timestamp: str
    raw: str = ""


class StepOutcome(BaseModel):
    step: TestStep
    commands_sent: List[Command] = Field(default_factory=list)
    responses: List[str] = Field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None


class TestResult(BaseModel):
    __test__ = False
    spec: TestSpec
    measurements: List[Measurement] = Field(default_factory=list)
    primary_measurement: Optional[Measurement] = None
    status: str = Field(description="PASS, FAIL, or ERROR")
    margin: Optional[float] = Field(default=None, description="Margin delta or percentage to limit")
    margin_str: str = ""
    notes: str = ""
    steps_outcomes: List[StepOutcome] = Field(default_factory=list)
    diagnosis: Optional[str] = Field(default=None, description="LLM failure diagnosis if status is FAIL")
    execution_time_sec: float = 0.0
