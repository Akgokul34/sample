from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.result import Result
from backend.app.schemas.result import ResultResponse

router = APIRouter()

@router.get("/", response_model=list[ResultResponse])
async def list_results(
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin", "operator", "viewer")),
):
    # Order results by created_at descending (newest first)
    stmt = select(Result).order_by(Result.created_at.desc())
    result = await db.execute(stmt)
    results = result.scalars().all()
    
    # Convert UUIDs to strings for Pydantic response compatibility
    for r in results:
        r.id = str(r.id)
        r.machine_id = str(r.machine_id)
        if r.order_id:
            r.order_id = str(r.order_id)
        if r.patient_id:
            r.patient_id = str(r.patient_id)
            
    return results

@router.delete("/clear")
async def clear_results(
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("admin")),
):
    stmt = delete(Result)
    await db.execute(stmt)
    await db.commit()
    return {"message": "All results cleared successfully"}
