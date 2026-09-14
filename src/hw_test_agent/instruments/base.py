"""
Abstract Base Class for hardware instruments.
"""

from abc import ABC, abstractmethod
from typing import Optional


class Instrument(ABC):
    """Abstract interface for all hardware and simulated instruments."""

    @abstractmethod
    def connect(self) -> None:
        """Establishes connection to the instrument."""
        pass

    @abstractmethod
    def write(self, command: str) -> None:
        """Sends an SCPI write command without expecting a text reply."""
        pass

    @abstractmethod
    def query(self, command: str) -> str:
        """Sends an SCPI query command and returns response string."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes the instrument session safely."""
        pass

    @abstractmethod
    def identify(self) -> str:
        """Returns identification string (*IDN?)."""
        pass

    @abstractmethod
    def check_error(self) -> Optional[str]:
        """Queries error queue (SYST:ERR?). Returns error message or None."""
        pass
