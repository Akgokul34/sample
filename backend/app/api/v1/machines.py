from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.machine import Machine
from backend.app.schemas.machine import MachineCreate, MachineResponse
import uuid

router = APIRouter()

@router.get("/", response_model=list[MachineResponse])
async def list_machines(
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator", "viewer")),
):
    result = await db.execute(select(Machine))
    machines = result.scalars().all()
    # Convert UUIDs to strings for Pydantic
    for m in machines:
        m.id = str(m.id)
    return machines

@router.post("/", response_model=MachineResponse)
async def create_machine(
    machine_in: MachineCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin")),
):
    db_machine = Machine(**machine_in.dict())
    db.add(db_machine)
    await db.commit()
    await db.refresh(db_machine)
    db_machine.id = str(db_machine.id)
    return db_machine
