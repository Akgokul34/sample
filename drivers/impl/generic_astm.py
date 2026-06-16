import logging
from typing import List, Optional
from backend.app.core.database import AsyncSessionLocal
from drivers.sdk.base import BaseDriver, RawMessage, ParsedResult
from backend.app.communication.astm.parser import ASTMParser, QueryRecord, ResultRecord
from backend.app.communication.astm.parser import OrderRecord
from backend.app.core.workflow import HostQueryHandler
from backend.app.core.validation import ValidationEngine
from backend.app.core.mapping import MappingEngine
from backend.app.models.result import Result
from backend.app.models.patient import Order
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

class GenericASTMDriver(BaseDriver):
    vendor = "Generic"
    protocol = "ASTM"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def parse_message(self, raw: RawMessage) -> List[ParsedResult]:
        pass

    async def process_message(self, raw_payload: str, machine_id: str) -> Optional[str]:
        """
        Process the raw ASTM payload, routing QueryRecords to HostQueryHandler
        and ResultRecords to the database via Mapping and Validation engines.
        Returns the ASTM response payload to be transmitted back, if any.
        """
        try:
            records = ASTMParser.parse_message(raw_payload)
            response_payload = None
            
            # Process Query Records (Host Query)
            for record in records:
                if isinstance(record, QueryRecord):
                    response_payload = await HostQueryHandler.process_astm_query(record.barcode)
                    logger.info(f"[{self.vendor} Driver] Generated Host Query Response for {record.barcode}")
                    
            # Process Result Records (Result Upload)
            validation_engine = ValidationEngine()
            current_accession = next((record.barcode for record in records if isinstance(record, OrderRecord)), None)
            
            async with AsyncSessionLocal() as session:
                mapping_engine = MappingEngine(session)
                results_count = 0
                order = None
                if current_accession:
                    order_result = await session.execute(
                        select(Order).where(Order.accession_number == current_accession)
                    )
                    order = order_result.scalars().first()
                
                for record in records:
                    if isinstance(record, ResultRecord):
                        canonical_code = await mapping_engine.map_test_code(machine_id, record.test_code)
                        flag = validation_engine.validate_result(canonical_code, record.value)
                        processing_status = "accepted" if order else "quarantined"
                        error_reason = None if order else "No matching order/accession for ASTM result"
                        
                        db_result = Result(
                            machine_id=machine_id,
                            order_id=order.id if order else None,
                            patient_id=order.patient_id if order else None,
                            accession_number=current_accession,
                            raw_test_code=record.test_code,
                            test_code=canonical_code,
                            value=record.value,
                            unit=record.units,
                            flag=flag,
                            is_validated=False,
                            processing_status=processing_status,
                            error_reason=error_reason
                        )
                        session.add(db_result)
                        results_count += 1
                
                if results_count > 0:
                    await session.commit()
                    logger.info(f"[{self.vendor} Driver] Saved {results_count} results for machine {machine_id}")
                    
            return response_payload

        except Exception as e:
            logger.error(f"[{self.vendor} Driver] Error processing message: {e}")
            return None
