import logging

logger = logging.getLogger(__name__)

class ValidationEngine:
    def __init__(self):
        # In production, reference ranges come from the test dictionary in the DB
        self.reference_ranges = {
            "WBC": {"low": 4.5, "high": 11.0, "critical_low": 2.0, "critical_high": 30.0},
            "RBC": {"low": 4.2, "high": 5.4, "critical_low": 2.5, "critical_high": 7.0}
        }

    def validate_result(self, test_code: str, value: float) -> str:
        ranges = self.reference_ranges.get(test_code)
        if not ranges:
            return "N" # Normal / Unvalidated

        try:
            val = float(value)
        except ValueError:
            return "N"

        if val <= ranges["critical_low"] or val >= ranges["critical_high"]:
            flag = "C" # Critical
        elif val < ranges["low"]:
            flag = "L" # Low
        elif val > ranges["high"]:
            flag = "H" # High
        else:
            flag = "N" # Normal
            
        logger.info(f"Validation for {test_code}={value} resulted in flag: {flag}")
        return flag
