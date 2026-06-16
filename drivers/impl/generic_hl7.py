import logging
from typing import List, Optional
from backend.app.core.database import AsyncSessionLocal
from drivers.sdk.base import BaseDriver, RawMessage, ParsedResult
from backend.app.communication.hl7.parser import HL7Parser, MSHSegment, OBXSegment, OBRSegment
from backend.app.core.validation import ValidationEngine
from backend.app.core.mapping import MappingEngine
from backend.app.models.result import Result
from backend.app.models.patient import Order
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

class GenericHL7Driver(BaseDriver):
    vendor = "Generic"
    protocol = "HL7"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def parse_message(self, raw: RawMessage) -> List[ParsedResult]:
        pass

    async def process_message(self, raw_payload: str, machine_id: str) -> Optional[str]:
        """
        Process the raw HL7 payload, routing ORU to the database via Mapping and Validation engines.
        Returns the ACK payload to be transmitted back.
        """
        try:
            parsed_objects, field_separator = HL7Parser.parse_message(raw_payload)
            msh = next((obj for obj in parsed_objects if isinstance(obj, MSHSegment)), None)
            
            if not msh:
                logger.error(f"[{self.vendor} Driver] No MSH segment found in HL7 message!")
                return "MSH|^~\\&|||||||ACK||Unknown\rMSA|AE|Unknown|No MSH Segment\r"
                
            if msh.message_type.startswith("ORU"):
                logger.info(f"[{self.vendor} Driver] Processing ORU Result Message")
                validation_engine = ValidationEngine()
                accession_number = next((obj.order_id for obj in parsed_objects if isinstance(obj, OBRSegment)), None)
                
                async with AsyncSessionLocal() as session:
                    mapping_engine = MappingEngine(session)
                    results_count = 0
                    order = None
                    if accession_number:
                        order_result = await session.execute(
                            select(Order).where(Order.accession_number == accession_number)
                        )
                        order = order_result.scalars().first()
                    
                    for obj in parsed_objects:
                        if isinstance(obj, OBXSegment):
                            canonical_code = await mapping_engine.map_test_code(machine_id, obj.test_code)
                            flag = validation_engine.validate_result(canonical_code, obj.result_value)
                            processing_status = "accepted" if order else "quarantined"
                            error_reason = None if order else "No matching order/accession for HL7 result"
                            
                            db_result = Result(
                                machine_id=machine_id,
                                order_id=order.id if order else None,
                                patient_id=order.patient_id if order else None,
                                accession_number=accession_number,
                                raw_test_code=obj.test_code,
                                test_code=canonical_code,
                                value=obj.result_value,
                                unit=obj.units,
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
                        
                return HL7Parser.generate_ack(msh, ack_code="AA", text_msg="Message accepted", field_separator=field_separator)
                        
            elif msh.message_type.startswith("ORM") or msh.message_type.startswith("ADT"):
                logger.warning(f"[{self.vendor} Driver] Unsupported HL7 message type: {msh.message_type}")
                return HL7Parser.generate_ack(msh, ack_code="AE", text_msg=f"Unsupported message type: {msh.message_type}", field_separator=field_separator)
                
            logger.warning(f"[{self.vendor} Driver] Unknown HL7 message type: {msh.message_type}")
            return HL7Parser.generate_ack(msh, ack_code="AE", text_msg=f"Unknown message type: {msh.message_type}", field_separator=field_separator)

        except Exception as e:
            logger.error(f"[{self.vendor} Driver] Error processing message: {e}")
            try:
                parsed_objects, field_separator = HL7Parser.parse_message(raw_payload)
                msh = next((obj for obj in parsed_objects if isinstance(obj, MSHSegment)), None)
                if msh:
                    return HL7Parser.generate_ack(msh, ack_code="AE", text_msg=str(e), field_separator=field_separator)
            except Exception:
                pass
            return "MSH|^~\\&|||||19700101000000||ACK|ACK-ERROR|P|2.3\rMSA|AE|Unknown|Processing error\r"
