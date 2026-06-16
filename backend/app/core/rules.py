import logging

logger = logging.getLogger(__name__)

class RuleEngine:
    @staticmethod
    def evaluate(test_code: str, value: str, flag: str):
        if flag == "C":
            logger.warning(f"CRITICAL ALERT: {test_code} value is {value} (Critical)")
            # Here we would publish to RabbitMQ or trigger an SMS/email alert
            return "ALERT_TRIGGERED"
        return "OK"
