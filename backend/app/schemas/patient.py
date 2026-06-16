from pydantic import BaseModel
from typing import Optional
from datetime import date

class PatientCreate(BaseModel):
    mrn: Optional[str] = None
    first_name: str
    last_name: str
    dob: Optional[date] = None

class PatientResponse(PatientCreate):
    id: str
    mrn: str # Always returned in response

    class Config:
        orm_mode = True

class OrderCreate(BaseModel):
    accession_number: Optional[str] = None

class OrderResponse(OrderCreate):
    id: str
    patient_id: str
    status: str
    accession_number: str # Always returned in response

    class Config:
        orm_mode = True
