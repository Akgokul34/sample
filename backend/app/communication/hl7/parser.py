from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
import uuid

@dataclass
class MSHSegment:
    sending_app: str
    receiving_app: str
    message_type: str
    message_control_id: str

@dataclass
class PIDSegment:
    patient_id: str
    patient_name: str

@dataclass
class OBRSegment:
    order_id: str

@dataclass
class OBXSegment:
    test_code: str
    result_value: str
    units: str

class HL7Parser:
    """
    Object-oriented HL7 parser.
    """
    @staticmethod
    def parse_message(raw_message: str):
        segments = raw_message.split('\r')
        parsed_objects = []
        
        field_separator = '|'
        
        # 1. Dynamic Parsing of Separators
        for segment in segments:
            if segment.startswith("MSH"):
                if len(segment) >= 4:
                    field_separator = segment[3]
                break
                
        for segment in segments:
            if not segment:
                continue
            fields = segment.split(field_separator)
            fields += [''] * (30 - len(fields)) # Pad
            
            if segment.startswith("MSH"):
                parsed_objects.append(MSHSegment(
                    sending_app=fields[2], 
                    receiving_app=fields[4], 
                    message_type=fields[8], 
                    message_control_id=fields[9]
                ))
            elif segment.startswith("PID"):
                parsed_objects.append(PIDSegment(patient_id=fields[3], patient_name=fields[5]))
            elif segment.startswith("OBR"):
                parsed_objects.append(OBRSegment(order_id=fields[3] or fields[2]))
            elif segment.startswith("OBX"):
                parsed_objects.append(OBXSegment(test_code=fields[3], result_value=fields[5], units=fields[6]))
                
        return parsed_objects, field_separator

    @staticmethod
    def generate_ack(original_msh: MSHSegment, ack_code: str = "AA", text_msg: str = "Message accepted", field_separator: str = "|") -> str:
        """Dynamically generate a mathematically correct ACK based on the incoming MSH."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        control_id = f"ACK-{uuid.uuid4()}"
        msh_ack = f"MSH{field_separator}^~\\&{field_separator}{original_msh.receiving_app}{field_separator}{field_separator}{original_msh.sending_app}{field_separator}{field_separator}{timestamp}{field_separator}{field_separator}ACK{field_separator}{control_id}{field_separator}P{field_separator}2.3"
        msa = f"MSA{field_separator}{ack_code}{field_separator}{original_msh.message_control_id}{field_separator}{text_msg}"
        return f"{msh_ack}\r{msa}\r"
