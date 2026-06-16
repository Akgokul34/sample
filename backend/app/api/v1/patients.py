from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.patient import Patient, Order
from backend.app.schemas.patient import PatientCreate, PatientResponse, OrderCreate, OrderResponse
import uuid
import random
import string
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=PatientResponse)
async def register_patient(
    patient_in: PatientCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator")),
):
    mrn = patient_in.mrn
    if not mrn:
        while True:
            rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            mrn = f"MRN-{datetime.now().strftime('%Y%m%d')}-{rand_suffix}"
            stmt = select(Patient).where(Patient.mrn == mrn)
            res = await db.execute(stmt)
            if not res.scalars().first():
                break
    else:
        # Check if MRN exists
        stmt = select(Patient).where(Patient.mrn == mrn)
        result = await db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="MRN already registered")
        
    db_patient = Patient(
        mrn=mrn,
        first_name=patient_in.first_name,
        last_name=patient_in.last_name,
        dob=patient_in.dob
    )
    db.add(db_patient)
    await db.commit()
    await db.refresh(db_patient)
    db_patient.id = str(db_patient.id)
    return db_patient

@router.get("/", response_model=list[PatientResponse])
async def list_patients(
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator", "viewer")),
):
    result = await db.execute(select(Patient))
    patients = result.scalars().all()
    for p in patients:
        p.id = str(p.id)
    return patients

@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator", "viewer")),
):
    result = await db.execute(select(Order))
    orders = result.scalars().all()
    for o in orders:
        o.id = str(o.id)
        o.patient_id = str(o.patient_id)
    return orders

@router.post("/{patient_id}/orders", response_model=OrderResponse)
async def create_order(
    patient_id: str,
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator")),
):
    accession_number = order_in.accession_number
    if not accession_number:
        while True:
            rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            accession_number = f"ACC-{datetime.now().strftime('%Y%m%d')}-{rand_suffix}"
            stmt = select(Order).where(Order.accession_number == accession_number)
            res = await db.execute(stmt)
            if not res.scalars().first():
                break
    else:
        # Check if accession number exists
        stmt = select(Order).where(Order.accession_number == accession_number)
        result = await db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Accession number already exists")
            
    db_order = Order(
        patient_id=patient_id,
        accession_number=accession_number
    )
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    db_order.id = str(db_order.id)
    db_order.patient_id = str(db_order.patient_id)
    return db_order
