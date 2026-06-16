from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import List, Optional

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class RawMessage:
    payload: bytes
    received_at: datetime
    machine_id: str

@dataclass
class ParsedResult:
    sample_id: str
    test_code: str
    value: str
    unit: Optional[str]
    flags: List[str]
    observed_at: datetime

class BaseDriver(ABC):
    vendor: str
    protocol: str

    def __init__(self, machine_config: dict):
        self.config = machine_config
        self.state = ConnectionState.DISCONNECTED

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    def parse_message(self, raw: RawMessage) -> List[ParsedResult]:
        pass

    @abstractmethod
    async def process_message(self, raw_payload: str, machine_id: str) -> Optional[str]:
        """Process the raw message, execute workflow (DB, Mapping, Validation). Return a response payload if needed."""
        pass
