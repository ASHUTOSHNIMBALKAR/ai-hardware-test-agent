"""
SCPI Command Generator mapping TestSteps to validated SCPI commands using command_db.yaml.
"""

import os
from typing import List, Dict, Any
import yaml
from hw_test_agent.models.schemas import TestStep, Command, ActionType
from hw_test_agent.utils.logging_setup import logger

COMMAND_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "instruments", "command_db.yaml")


def load_command_db() -> Dict[str, Any]:
    """Loads SCPI command templates from YAML database."""
    if os.path.exists(COMMAND_DB_PATH):
        try:
            with open(COMMAND_DB_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load command_db.yaml: {e}")

    # Default fallback database mapping
    return {
        "psu": {
            "set_voltage": "VOLT {value}",
            "set_current_limit": "CURR {value}",
            "output_on": "OUTP ON",
            "output_off": "OUTP OFF",
            "measure_voltage": "MEAS:VOLT?",
            "measure_current": "MEAS:CURR?",
        },
        "scope": {
            "coupling_ac": "CHAN1:COUP AC",
            "coupling_dc": "CHAN1:COUP DC",
            "timebase": "TIM:SCAL {value}",
            "vertical_scale": "CHAN1:SCAL {value}",
            "measure_vpp": "MEAS:VPP? CHAN1",
            "measure_freq": "MEAS:FREQ? CHAN1",
        },
    }


def generate_commands(step: TestStep) -> List[Command]:
    """Converts a TestStep into one or more SCPI Command objects."""
    db = load_command_db()
    commands: List[Command] = []

    act = step.action
    params = step.params

    if act == ActionType.SET_SUPPLY:
        val = params.get("value", 3.3)
        scpi_tmpl = db["psu"].get("set_voltage", "VOLT {value}")
        commands.append(
            Command(
                instrument="psu",
                scpi=scpi_tmpl.format(value=val),
                expects_response=False,
                description=f"Set power supply voltage to {val}V",
            )
        )

    elif act == ActionType.SET_CURRENT_LIMIT:
        val = params.get("value", 1.0)
        scpi_tmpl = db["psu"].get("set_current_limit", "CURR {value}")
        commands.append(
            Command(
                instrument="psu",
                scpi=scpi_tmpl.format(value=val),
                expects_response=False,
                description=f"Set power supply current limit to {val}A",
            )
        )

    elif act == ActionType.ENABLE_OUTPUT:
        scpi_tmpl = db["psu"].get("output_on", "OUTP ON")
        commands.append(
            Command(
                instrument="psu",
                scpi=scpi_tmpl,
                expects_response=False,
                description="Enable power supply output",
            )
        )

    elif act == ActionType.DISABLE_OUTPUT:
        scpi_tmpl = db["psu"].get("output_off", "OUTP OFF")
        commands.append(
            Command(
                instrument="psu",
                scpi=scpi_tmpl,
                expects_response=False,
                description="Disable power supply output",
            )
        )

    elif act == ActionType.CONFIGURE_SCOPE:
        if "coupling" in params:
            coup = str(params["coupling"]).upper()
            scpi_cmd = "CHAN1:COUP AC" if coup == "AC" else "CHAN1:COUP DC"
            commands.append(Command(instrument="scope", scpi=scpi_cmd, expects_response=False, description=f"Set scope coupling to {coup}"))

        if "vertical_scale" in params:
            vscale = params["vertical_scale"]
            scpi_tmpl = db["scope"].get("vertical_scale", "CHAN1:SCAL {value}")
            commands.append(Command(instrument="scope", scpi=scpi_tmpl.format(value=vscale), expects_response=False, description=f"Set vertical scale {vscale}V/div"))

        if "timebase" in params:
            tb = params["timebase"]
            scpi_tmpl = db["scope"].get("timebase", "TIM:SCAL {value}")
            commands.append(Command(instrument="scope", scpi=scpi_tmpl.format(value=tb), expects_response=False, description=f"Set timebase {tb}s/div"))

    elif act == ActionType.MEASURE:
        target = str(params.get("target", "voltage")).lower()
        inst_type = str(params.get("instrument", "psu")).lower()

        if target in ["vpp", "ripple"]:
            scpi_tmpl = db["scope"].get("measure_vpp", "MEAS:VPP? CHAN1")
            commands.append(Command(instrument="scope", scpi=scpi_tmpl, expects_response=True, description="Query peak-to-peak ripple voltage"))
        elif target in ["freq", "frequency"]:
            scpi_tmpl = db["scope"].get("measure_freq", "MEAS:FREQ? CHAN1")
            commands.append(Command(instrument="scope", scpi=scpi_tmpl, expects_response=True, description="Query frequency"))
        elif target in ["current", "curr"]:
            scpi_tmpl = db["psu"].get("measure_current", "MEAS:CURR?")
            commands.append(Command(instrument="psu", scpi=scpi_tmpl, expects_response=True, description="Query DC current draw"))
        else:
            scpi_tmpl = db["psu"].get("measure_voltage", "MEAS:VOLT?")
            commands.append(Command(instrument="psu", scpi=scpi_tmpl, expects_response=True, description="Query DC voltage"))

    return commands
