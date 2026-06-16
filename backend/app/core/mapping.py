import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.models.dictionary import MachineTestMapping
from backend.app.models.machine import Machine

logger = logging.getLogger(__name__)

class MappingEngine:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def map_test_code(self, machine_id: str, raw_code: str) -> str:
        stmt = select(MachineTestMapping).where(
            MachineTestMapping.machine_id == machine_id,
            MachineTestMapping.vendor_code == raw_code
        )
        result = await self.db.execute(stmt)
        mapping = result.scalars().first()
        
        if mapping:
            logger.info(f"Mapped code '{raw_code}' -> '{mapping.canonical_code}' for machine {machine_id}")
            return mapping.canonical_code
            
        # Fallback if no mapping exists
        logger.warning(f"No mapping found for code '{raw_code}' on machine {machine_id}")
        return raw_code
