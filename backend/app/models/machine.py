from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from backend.app.models.base import BaseModel

class Machine(BaseModel):
    __tablename__ = "machines"

    name = Column(String, nullable=False)
    vendor = Column(String, nullable=False)
    protocol = Column(String, nullable=False) # ASTM, HL7
    transport = Column(String, nullable=False) # TCP, SERIAL
    ip_address = Column(String)
    port = Column(Integer)
    is_active = Column(Boolean, default=True)

class MachineConfig(BaseModel):
    __tablename__ = "machine_configs"
    
    machine_id = Column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    config_key = Column(String, nullable=False)
    config_value = Column(JSONB, nullable=False)

class ConnectionLog(BaseModel):
    __tablename__ = "connection_logs"
    
    machine_id = Column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    ip_address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    status = Column(String, nullable=False) # "connected", "disconnected"

class RawMessage(BaseModel):
    __tablename__ = "raw_messages"
    
    machine_id = Column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    direction = Column(String, nullable=False) # "inbound", "outbound"
    payload = Column(String, nullable=False) # Store the decoded raw bytes
