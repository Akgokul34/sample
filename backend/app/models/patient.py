from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.models.base import BaseModel

class Patient(BaseModel):
    __tablename__ = "patients"

    mrn = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dob = Column(Date)
    
    orders = relationship("Order", back_populates="patient")

class Order(BaseModel):
    __tablename__ = "orders"
    
    patient_id = Column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    accession_number = Column(String, unique=True, index=True, nullable=False) # This is the barcode
    status = Column(String, default="received")
    
    patient = relationship("Patient", back_populates="orders")
