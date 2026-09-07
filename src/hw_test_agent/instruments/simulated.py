"""
Simulated Power Supply and Oscilloscope with state tracking, realistic noise, and fault injection.
"""

import math
import random
from typing import Optional
from hw_test_agent.instruments.base import Instrument
from hw_test_agent.utils.logging_setup import logger


class SimulatedPSU(Instrument):
    """Simulated Programmable DC Power Supply."""

    def __init__(self, name: str = "Simulated_PSU_DP832"):
        self.name = name
        self.connected = False
        self.set_voltage_val = 3.3
        self.set_current_limit_val = 1.0
        self.output_on = False
        self.load_resistance = 50.0  # Ohms
        self.fault_mode: Optional[str] = None

    def connect(self) -> None:
        self.connected = True
        logger.info(f"Connected to {self.name}")

    def write(self, command: str) -> None:
        if not self.connected:
            self.connect()

        cmd = command.strip().upper()
        logger.debug(f"[{self.name}] WRITE: {command}")

        if cmd.startswith("VOLT "):
            try:
                val = float(cmd.split()[1])
                self.set_voltage_val = val
            except Exception as e:
                logger.error(f"Invalid VOLT command: {command} ({e})")
        elif cmd.startswith("CURR "):
            try:
                val = float(cmd.split()[1])
                self.set_current_limit_val = val
            except Exception as e:
                logger.error(f"Invalid CURR command: {command} ({e})")
        elif cmd == "OUTP ON":
            self.output_on = True
        elif cmd == "OUTP OFF":
            self.output_on = False
        elif cmd == "*RST":
            self.set_voltage_val = 0.0
            self.output_on = False

    def query(self, command: str) -> str:
        if not self.connected:
            self.connect()

        cmd = command.strip().upper()
        logger.debug(f"[{self.name}] QUERY: {command}")

        if cmd == "*IDN?":
            return f"RIGOL TECHNOLOGIES,{self.name},SIM123456,01.00"
        elif cmd == "*ESR?":
            return "0"
        elif cmd == "SYST:ERR?":
            return '0,"No error"'
        elif cmd in ("MEAS:VOLT?", "MEAS:VOLT:DC?"):
            if not self.output_on:
                val = abs(random.gauss(0.001, 0.0005))
            else:
                if self.fault_mode == "voltage_drop":
                    val = self.set_voltage_val * 0.85 + random.gauss(0, 0.01)
                else:
                    val = self.set_voltage_val + random.gauss(0, 0.002)
            return f"{val:.5f}"
        elif cmd in ("MEAS:CURR?", "MEAS:CURR:DC?"):
            if not self.output_on:
                val = 0.0
            else:
                expected_curr = self.set_voltage_val / self.load_resistance
                if self.fault_mode == "current_overload":
                    expected_curr = self.set_current_limit_val + 0.2
                val = min(expected_curr, self.set_current_limit_val) + random.gauss(0, 0.0005)
            return f"{val:.5f}"
        else:
            return "0.0"

    def identify(self) -> str:
        return self.query("*IDN?")

    def check_error(self) -> Optional[str]:
        err = self.query("SYST:ERR?")
        return None if '0,"No error"' in err or err == "0" else err

    def close(self) -> None:
        self.output_on = False
        self.connected = False
        logger.info(f"Closed {self.name}")

    def inject_fault(self, fault_type: Optional[str]) -> None:
        """Injects simulated fault e.g., 'voltage_drop', 'current_overload'."""
        self.fault_mode = fault_type
        logger.warning(f"Injected fault into {self.name}: {fault_type}")


class SimulatedScope(Instrument):
    """Simulated Oscilloscope."""

    def __init__(self, name: str = "Simulated_Scope_DSOX1204G"):
        self.name = name
        self.connected = False
        self.coupling = "DC"
        self.timebase = 1e-3  # 1 ms
        self.vertical_scale = 1.0  # 1 V/div
        self.base_vpp = 0.022  # 22 mV nominal ripple
        self.base_freq = 1000.0  # 1 kHz nominal signal
        self.fault_mode: Optional[str] = None
        self.psu_ref: Optional[SimulatedPSU] = None

    def connect(self) -> None:
        self.connected = True
        logger.info(f"Connected to {self.name}")

    def write(self, command: str) -> None:
        if not self.connected:
            self.connect()

        cmd = command.strip().upper()
        logger.debug(f"[{self.name}] WRITE: {command}")

        if "COUP AC" in cmd:
            self.coupling = "AC"
        elif "COUP DC" in cmd:
            self.coupling = "DC"
        elif cmd.startswith("TIM:SCAL "):
            try:
                self.timebase = float(cmd.split()[-1])
            except Exception:
                pass
        elif cmd.startswith("CHAN1:SCAL "):
            try:
                self.vertical_scale = float(cmd.split()[-1])
            except Exception:
                pass

    def query(self, command: str) -> str:
        if not self.connected:
            self.connect()

        cmd = command.strip().upper()
        logger.debug(f"[{self.name}] QUERY: {command}")

        if cmd == "*IDN?":
            return f"KEYSIGHT TECHNOLOGIES,{self.name},MY59001234,02.10"
        elif cmd == "*ESR?":
            return "0"
        elif cmd == "SYST:ERR?":
            return '0,"No error"'
        elif "MEAS:VPP?" in cmd:
            # Check PSU state if linked
            psu_on = self.psu_ref.output_on if self.psu_ref else True
            if not psu_on:
                vpp = random.gauss(0.002, 0.0005)
            elif self.fault_mode == "high_ripple":
                vpp = 0.085 + random.gauss(0, 0.005)  # 85 mV ripple (triggers test failure!)
            else:
                vpp = self.base_vpp + random.gauss(0, 0.002)
            return f"{vpp:.5f}"
        elif "MEAS:FREQ?" in cmd:
            if self.fault_mode == "freq_drift":
                freq = 1050.0 + random.gauss(0, 10.0)
            else:
                freq = self.base_freq + random.gauss(0, 2.0)
            return f"{freq:.2f}"
        else:
            return "0.0"

    def identify(self) -> str:
        return self.query("*IDN?")

    def check_error(self) -> Optional[str]:
        err = self.query("SYST:ERR?")
        return None if '0,"No error"' in err or err == "0" else err

    def close(self) -> None:
        self.connected = False
        logger.info(f"Closed {self.name}")

    def inject_fault(self, fault_type: Optional[str]) -> None:
        """Injects simulated fault e.g., 'high_ripple', 'freq_drift'."""
        self.fault_mode = fault_type
        logger.warning(f"Injected fault into {self.name}: {fault_type}")
