from dataclasses import dataclass
from typing import List, Optional

@dataclass
class HeaderRecord:
    sender: str
    receiver: str
    
@dataclass
class PatientRecord:
    patient_id: str
    
@dataclass
class OrderRecord:
    barcode: str
    test_ids: List[str]
    
@dataclass
class ResultRecord:
    test_code: str
    value: str
    units: str
    
@dataclass
class QueryRecord:
    barcode: str

class ASTMParser:
    """
    Object-oriented ASTM E1394 logical parser.
    Converts raw text into validated Python dataclasses.
    """
    @staticmethod
    def parse_message(raw_message: str) -> List[any]:
        records = raw_message.split('\r')
        parsed_objects = []
        
        for record in records:
            if not record:
                continue
            record_type = record[0]
            fields = record.split('|')
            
            # Pad fields to avoid IndexError if the machine didn't send trailing pipes
            fields += [''] * (30 - len(fields)) 
            
            if record_type == 'H':
                parsed_objects.append(HeaderRecord(sender=fields[4], receiver=fields[9]))
            elif record_type == 'P':
                parsed_objects.append(PatientRecord(patient_id=fields[3]))
            elif record_type == 'O':
                parsed_objects.append(OrderRecord(barcode=fields[2], test_ids=[fields[4]]))
            elif record_type == 'R':
                parsed_objects.append(ResultRecord(test_code=fields[2], value=fields[3], units=fields[4]))
            elif record_type == 'Q':
                # ASTM Query typically puts the barcode in the 3rd field, sometimes prefixed with ^
                barcode_field = fields[2]
                clean_barcode = barcode_field.split('^')[1] if '^' in barcode_field else barcode_field
                parsed_objects.append(QueryRecord(barcode=clean_barcode))
                
        return parsed_objects
