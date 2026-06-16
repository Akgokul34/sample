from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ResultResponse(BaseModel):
    id: str
    machine_id: str
    order_id: Optional[str] = None
    patient_id: Optional[str] = None
    accession_number: Optional[str] = None
    test_code: str
    raw_test_code: str
    value: str
    unit: Optional[str] = None
    flag: Optional[str] = None
    is_validated: bool
    processing_status: str
    error_reason: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
