from sqlalchemy import Column, String, Boolean, ForeignKey
from backend.app.models.base import BaseModel

class Result(BaseModel):
    __tablename__ = "results"

    machine_id = Column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True)
    patient_id = Column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=True) # Can be null if unmatched
    accession_number = Column(String, index=True, nullable=True) # The barcode
    
    test_code = Column(String, nullable=False) # e.g., WBC (Canonical after mapping)
    raw_test_code = Column(String, nullable=False) # e.g., LEU (Vendor specific)
    
    value = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    flag = Column(String, nullable=True) # N, H, L, C
    
    is_validated = Column(Boolean, default=False)
    processing_status = Column(String, nullable=False, default="quarantined") # accepted, quarantined, rejected
    error_reason = Column(String, nullable=True)
