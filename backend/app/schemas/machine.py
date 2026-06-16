from pydantic import BaseModel
from typing import Optional

class MachineCreate(BaseModel):
    name: str
    vendor: str
    protocol: str
    transport: str
    ip_address: Optional[str] = None
    port: Optional[int] = None
    is_active: bool = True

class MachineResponse(MachineCreate):
    id: str

    class Config:
        orm_mode = True
