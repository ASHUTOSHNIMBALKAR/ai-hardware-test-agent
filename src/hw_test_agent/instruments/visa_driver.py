"""
PyVISA hardware instrument driver implementation.
"""

import logging
from typing import Optional, List
import pyvisa
from pyvisa.errors import VisaIOError
from hw_test_agent.instruments.base import Instrument
from hw_test_agent.utils.logging_setup import logger


def list_resources(backend: str = "") -> List[str]:
    """Lists available PyVISA resources."""
    try:
        rm = pyvisa.ResourceManager(backend)
        return list(rm.list_resources())
    except Exception as e:
        logger.error(f"Error listing VISA resources: {e}")
        return []


class VisaInstrument(Instrument):
    """Driver for physical hardware instruments connected via PyVISA."""

    def __init__(self, resource_name: str, backend: str = "", timeout_ms: int = 5000):
        self.resource_name = resource_name
        self.backend = backend
        self.timeout_ms = timeout_ms
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst: Optional[pyvisa.resources.Resource] = None

    def connect(self) -> None:
        """Opens connection to PyVISA resource."""
        try:
            self.rm = pyvisa.ResourceManager(self.backend)
            self.inst = self.rm.open_resource(self.resource_name)
            self.inst.timeout = self.timeout_ms
            self.inst.read_termination = "\n"
            self.inst.write_termination = "\n"
            logger.info(f"Connected to VISA instrument: {self.resource_name}")
        except VisaIOError as e:
            logger.error(f"Failed to connect to {self.resource_name}: {e}")
            raise

    def write(self, command: str) -> None:
        """Sends write command."""
        if not self.inst:
            self.connect()
        try:
            logger.debug(f"[{self.resource_name}] WRITE: {command}")
            self.inst.write(command)
        except VisaIOError as e:
            logger.error(f"[{self.resource_name}] Write failed: {command} -> {e}")
            raise

    def query(self, command: str) -> str:
        """Sends query command and returns response."""
        if not self.inst:
            self.connect()
        try:
            logger.debug(f"[{self.resource_name}] QUERY: {command}")
            res = self.inst.query(command).strip()
            logger.debug(f"[{self.resource_name}] READ: {res}")
            return res
        except VisaIOError as e:
            logger.error(f"[{self.resource_name}] Query failed: {command} -> {e}")
            raise

    def identify(self) -> str:
        """Queries *IDN?."""
        return self.query("*IDN?")

    def check_error(self) -> Optional[str]:
        """Queries SYST:ERR?."""
        try:
            err = self.query("SYST:ERR?")
            if "0" in err or "No error" in err:
                return None
            return err
        except Exception:
            return None

    def close(self) -> None:
        """Closes VISA session."""
        if self.inst:
            try:
                self.inst.close()
            except Exception:
                pass
            self.inst = None
        if self.rm:
            try:
                self.rm.close()
            except Exception:
                pass
            self.rm = None
        logger.info(f"Closed VISA connection: {self.resource_name}")
