from sqlalchemy import Column, String, ForeignKey
from backend.app.models.base import BaseModel

class TestDictionary(BaseModel):
    __tablename__ = "test_dictionary"

    code = Column(String, unique=True, index=True, nullable=False) # e.g. "WBC"
    name = Column(String, nullable=False) # e.g. "White Blood Cells"
    unit = Column(String)

class MachineTestMapping(BaseModel):
    __tablename__ = "machine_test_mapping"

    machine_id = Column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    vendor_code = Column(String, nullable=False) # e.g. "LEU" coming from the machine
    canonical_code = Column(ForeignKey("test_dictionary.code", ondelete="CASCADE"), nullable=False)
