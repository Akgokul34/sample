import logging
from backend.app.core.database import AsyncSessionLocal
from sqlalchemy.future import select
from backend.app.models.patient import Order

logger = logging.getLogger(__name__)

class HostQueryHandler:
    @staticmethod
    async def process_astm_query(barcode: str) -> str:
        """
        Takes a barcode from a QueryRecord, looks up the Order in DB,
        and constructs the ASTM O record.
        """
        logger.info(f"Host Query received for barcode: {barcode}. Querying database...")
        async with AsyncSessionLocal() as db:
            stmt = select(Order).where(Order.accession_number == barcode)
            result = await db.execute(stmt)
            order = result.scalars().first()
            
            if order:
                logger.info(f"Order found in DB: {order.id}. Constructing O record.")
                # Construct an ASTM Order record
                # Format: O|1|barcode||ALL|||||||N||||||||||||||O
                return f"O|1|{barcode}||ALL|||||||N||||||||||||||O\r"
            else:
                logger.warning(f"No order found for barcode: {barcode}")
                # Construct empty order or cancellation
                return f"O|1|{barcode}|||||||||X||||||||||||||O\r"
