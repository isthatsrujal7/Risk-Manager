from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timezone


class FraudPatternType(str, Enum):
    PAYMENT_COLLAPSED = "payment_collapsed"
    STATUS_MISMATCH = "status_mismatch"
    GHOST_PAYMENT = "ghost_payment"
    SETTLEMENT_DELAY = "settlement_delay"
    VELOCITY_FRAUD = "velocity_fraud"
    ACCOUNT_TAKEOVER = "account_takeover"
    REFUND_ABUSE = "refund_abuse"
    CARD_TESTING = "card_testing"
    NO_PATTERN = "no_pattern"


PATTERN_DESCRIPTIONS = {
    FraudPatternType.PAYMENT_COLLAPSED: {
        "name": "Payment Collapsed",
        "description": "Transaction shows 'completed' to merchant but actual bank transfer failed or was cancelled. Receiver never gets the payment.",
        "severity": "CRITICAL",
        "example": "Customer pays Rs 5000 to merchant. Merchant sees 'Payment Successful' and ships goods. But the bank transfer actually failed — merchant loses goods + money.",
        "detection_signals": [
            "Payment confirmation timestamp vs actual settlement time gap",
            "Bank response code indicates failure but frontend showed success",
            "Merchant settlement never received",
            "UPI/bank reversal within 24 hours of transaction",
        ],
        "business_impact": "High — merchant ships goods without receiving payment",
    },
    FraudPatternType.STATUS_MISMATCH: {
        "name": "Status Mismatch",
        "description": "Payment status shown as 'completed' to customer but bank/processor shows 'failed' or 'pending'. The display status does not match actual status.",
        "severity": "HIGH",
        "example": "Customer pays on Razorpay. App shows green checkmark 'Payment Done'. But bank shows 'Transaction Failed'. Customer thinks payment is done.",
        "detection_signals": [
            "Frontend status != backend/bank status",
            "Confirmation sent before bank callback received",
            "Missing or delayed bank settlement notification",
            "Transaction marked complete without settlement confirmation",
        ],
        "business_impact": "Medium-High — customer confusion, potential double-payment or non-payment",
    },
    FraudPatternType.GHOST_PAYMENT: {
        "name": "Ghost Payment",
        "description": "Payment appears successful in the system but no actual fund movement occurred between accounts. A phantom transaction with no real money transfer.",
        "severity": "CRITICAL",
        "example": "System logs Rs 10,000 payment as successful. But checking bank statements shows no debit from customer and no credit to merchant. The transaction is a ghost.",
        "detection_signals": [
            "No corresponding bank debit/credit entry",
            "Settlement amount differs from transaction amount",
            "Bank reference number not found in bank records",
            "Transaction exists only in payment gateway logs",
        ],
        "business_impact": "Critical — total loss if goods/services delivered",
    },
    FraudPatternType.SETTLEMENT_DELAY: {
        "name": "Settlement Delay Fraud",
        "description": "Payment shows as processing/completed but settlement to merchant is artificially delayed or never happens. Exploits the delay window.",
        "severity": "HIGH",
        "example": "Payment marked 'completed' on day 1. Merchant expects settlement in T+1. But settlement is delayed indefinitely or reversed. Merchant already delivered goods.",
        "detection_signals": [
            "Transaction age > expected settlement window with no settlement",
            "Repeated settlement failures for same merchant",
            "Settlement amount decreasing across retries",
            "Merchant flagged for 'delayed settlement' complaints",
        ],
        "business_impact": "High — merchant cash flow disruption, potential loss",
    },
    FraudPatternType.VELOCITY_FRAUD: {
        "name": "Velocity Fraud",
        "description": "Multiple rapid transactions from same card/account suggesting card testing or brute-force amount extraction. Unusual transaction frequency.",
        "severity": "HIGH",
        "example": "5 transactions in 2 minutes from same card — Rs 1, Rs 1, Rs 100, Rs 1000, Rs 10000. Classic card testing pattern escalating amounts.",
        "detection_signals": [
            ">3 transactions in 5 minutes from same source",
            "Escalating amount pattern across rapid transactions",
            "Multiple merchants in short time window",
            "Small test transactions followed by large ones",
        ],
        "business_impact": "High — stolen card testing before large fraudulent purchase",
    },
    FraudPatternType.ACCOUNT_TAKEOVER: {
        "name": "Account Takeover",
        "description": "Legitimate customer account suddenly used from new device/location with different spending patterns. Account may be compromised.",
        "severity": "CRITICAL",
        "example": "Customer who only transacts from Mumbai suddenly has Rs 50,000 transaction from Lagos on a new device at 3 AM. Account is likely compromised.",
        "detection_signals": [
            "New device_id not in customer history",
            "Location >500km from usual location",
            "Transaction hour completely outside normal pattern",
            "Amount 5x+ above customer average",
            "All three (device, location, amount) changed simultaneously",
        ],
        "business_impact": "Critical — full account compromise, large unauthorized transactions",
    },
    FraudPatternType.REFUND_ABUSE: {
        "name": "Refund Abuse / Friendly Fraud",
        "description": "Customer makes legitimate payment, receives goods/services, then disputes or claims non-receipt to get refund. Also called 'friendly fraud'.",
        "severity": "MEDIUM",
        "example": "Customer buys electronics worth Rs 20,000, receives it, then files chargeback claiming 'payment done but goods not received'. Gets refund + goods.",
        "detection_signals": [
            "Customer has history of refund/chargeback claims",
            "Dispute filed after delivery confirmation",
            "Refund rate significantly above average for customer",
            "Pattern of disputes across multiple merchants",
        ],
        "business_impact": "Medium — merchant loses goods + payment",
    },
    FraudPatternType.CARD_TESTING: {
        "name": "Card Testing",
        "description": "Small-value transactions to test if stolen card details work before making large fraudulent purchase. Usually multiple small amounts.",
        "severity": "HIGH",
        "example": "Rs 1, Rs 5, Rs 10 transactions from same card within minutes. Testing if card is valid before Rs 50,000 purchase.",
        "detection_signals": [
            "Multiple transactions < Rs 100 in short window",
            "Different merchants for each small transaction",
            "Followed by (or preceded by) a much larger transaction",
            "Card used across different cities/countries rapidly",
        ],
        "business_impact": "High — precursor to large fraud",
    },
}


@dataclass
class FraudPatternResult:
    pattern_type: FraudPatternType
    confidence: float
    severity: str
    signals: List[Dict] = field(default_factory=list)
    explanation: str = ""
    is_merchant_risk: bool = False
    is_customer_risk: bool = False
    recommended_action: str = ""


class FraudPatternDetector:
    def __init__(self):
        self.patterns = PATTERN_DESCRIPTIONS

    def detect_all_patterns(self, transaction_data: dict, customer_history: list, recent_transactions: list) -> List[FraudPatternResult]:
        results = []

        r = self.detect_payment_collapsed(transaction_data, customer_history)
        if r: results.append(r)

        r = self.detect_status_mismatch(transaction_data)
        if r: results.append(r)

        r = self.detect_ghost_payment(transaction_data)
        if r: results.append(r)

        r = self.detect_settlement_delay(transaction_data, recent_transactions)
        if r: results.append(r)

        r = self.detect_velocity_fraud(recent_transactions, transaction_data)
        if r: results.append(r)

        r = self.detect_account_takeover(transaction_data, customer_history)
        if r: results.append(r)

        r = self.detect_card_testing(recent_transactions, transaction_data)
        if r: results.append(r)

        r = self.detect_refund_abuse(transaction_data, customer_history)
        if r: results.append(r)

        return results

    def detect_payment_collapsed(self, txn: dict, history: list) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        if txn.get("payment_status") == "completed" and txn.get("settlement_status") in ("pending", "failed", "none"):
            risk_score += 40
            signals.append({"signal": "settlement_missing", "weight": 0.4, "description": "Payment marked completed but no settlement record"})

        if txn.get("payment_method") in ("upi", "netbanking") and txn.get("amount", 0) > 10000:
            risk_score += 15
            signals.append({"signal": "high_value_no_settlement", "weight": 0.15, "description": f"High value Rs {txn.get('amount',0):,.0f} with settlement issue"})

        if txn.get("reversal_count", 0) > 0:
            risk_score += 25
            signals.append({"signal": "has_reversal", "weight": 0.25, "description": "Transaction had reversals"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.PAYMENT_COLLAPSED,
            confidence=min(1.0, risk_score / 100),
            severity="CRITICAL",
            signals=signals,
            explanation="Payment was marked as completed but the actual bank transfer may have failed or been cancelled. The merchant may have delivered goods without receiving real payment.",
            is_merchant_risk=True,
            recommended_action="HOLD",
        )

    def detect_status_mismatch(self, txn: dict) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        if txn.get("display_status") and txn.get("actual_status") and txn["display_status"] != txn["actual_status"]:
            risk_score += 50
            signals.append({"signal": "status_mismatch", "weight": 0.5, "description": f"Display shows '{txn['display_status']}' but actual is '{txn['actual_status']}'"})

        if txn.get("bank_callback_status") and txn.get("gateway_status") and txn["bank_callback_status"] != txn["gateway_status"]:
            risk_score += 30
            signals.append({"signal": "callback_mismatch", "weight": 0.3, "description": "Bank callback status differs from gateway status"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.STATUS_MISMATCH,
            confidence=min(1.0, risk_score / 100),
            severity="HIGH",
            signals=signals,
            explanation="The payment status displayed to the user does not match the actual processing status. This can cause customer confusion and incorrect assumptions about payment completion.",
            is_customer_risk=True,
            is_merchant_risk=True,
            recommended_action="REVIEW",
        )

    def detect_ghost_payment(self, txn: dict) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        if txn.get("settlement_status") == "none" and txn.get("payment_status") == "completed":
            risk_score += 45
            signals.append({"signal": "no_settlement_record", "weight": 0.45, "description": "Transaction completed but no settlement entry exists"})

        if txn.get("bank_ref_number") is None and txn.get("payment_status") == "completed":
            risk_score += 25
            signals.append({"signal": "no_bank_ref", "weight": 0.25, "description": "No bank reference number for completed transaction"})

        if txn.get("amount", 0) > txn.get("customer_avg_amount", 0) * 3 if txn.get("customer_avg_amount") else False:
            risk_score += 15
            signals.append({"signal": "amount_vs_settlement", "weight": 0.15, "description": "High amount with no settlement"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.GHOST_PAYMENT,
            confidence=min(1.0, risk_score / 100),
            severity="CRITICAL",
            signals=signals,
            explanation="Transaction appears successful in logs but no actual fund movement detected. This is a phantom transaction — the most dangerous type as it shows success without real payment.",
            is_merchant_risk=True,
            recommended_action="HOLD",
        )

    def detect_settlement_delay(self, txn: dict, recent: list) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        if txn.get("settlement_status") == "pending":
            risk_score += 25
            signals.append({"signal": "settlement_pending", "weight": 0.25, "description": "Settlement still pending"})

        if txn.get("age_hours", 0) > 48 and txn.get("settlement_status") == "pending":
            risk_score += 35
            signals.append({"signal": "delayed_settlement", "weight": 0.35, "description": f"Settlement pending for {txn.get('age_hours',0)} hours"})

        merchant_settlement_fails = sum(1 for t in recent if t.get("settlement_status") == "failed" and t.get("merchant_id") == txn.get("merchant_id"))
        if merchant_settlement_fails > 2:
            risk_score += 20
            signals.append({"signal": "repeated_settlement_failures", "weight": 0.2, "description": f"Merchant has {merchant_settlement_fails} failed settlements recently"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.SETTLEMENT_DELAY,
            confidence=min(1.0, risk_score / 100),
            severity="HIGH",
            signals=signals,
            explanation="Payment settlement is significantly delayed. Merchant may deliver goods before settlement, leading to potential loss if settlement eventually fails.",
            is_merchant_risk=True,
            recommended_action="REVIEW",
        )

    def detect_velocity_fraud(self, recent: list, current: dict) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        customer_id = current.get("customer_id")
        same_customer = [t for t in recent if t.get("customer_id") == customer_id]

        if len(same_customer) >= 3:
            risk_score += 20
            signals.append({"signal": "high_frequency", "weight": 0.2, "description": f"{len(same_customer)} recent transactions from same customer"})

        if len(same_customer) >= 5:
            risk_score += 30
            signals.append({"signal": "very_high_frequency", "weight": 0.3, "description": "5+ transactions in rapid succession"})

        if len(same_customer) >= 2:
            amounts = [t.get("amount", 0) for t in same_customer]
            if amounts and max(amounts) > min(amounts) * 10:
                risk_score += 25
                signals.append({"signal": "escalating_amounts", "weight": 0.25, "description": "Amounts escalating rapidly — classic testing pattern"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.VELOCITY_FRAUD,
            confidence=min(1.0, risk_score / 100),
            severity="HIGH",
            signals=signals,
            explanation="Unusually high transaction velocity detected. Multiple transactions in short window suggest card testing or brute-force fraud attempt.",
            is_customer_risk=True,
            recommended_action="REVIEW",
        )

    def detect_account_takeover(self, txn: dict, history: list) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []
        anomalies = 0

        if txn.get("device_id") and txn["device_id"] not in [h.get("device_id") for h in history if h.get("device_id")]:
            risk_score += 20
            anomalies += 1
            signals.append({"signal": "new_device", "weight": 0.2, "description": f"New device: {txn['device_id']}"})

        if txn.get("location_city") and txn["location_city"] not in [h.get("location_city") for h in history if h.get("location_city")]:
            risk_score += 20
            anomalies += 1
            signals.append({"signal": "new_location", "weight": 0.2, "description": f"New location: {txn['location_city']}"})

        if txn.get("timestamp"):
            hour = txn["timestamp"].hour if hasattr(txn["timestamp"], "hour") else 0
            normal_hours = [h.get("typical_hour", 12) for h in history]
            if normal_hours and hour not in range(min(normal_hours) - 2, max(normal_hours) + 3):
                risk_score += 15
                anomalies += 1
                signals.append({"signal": "unusual_hour", "weight": 0.15, "description": f"Transaction at unusual hour: {hour}:00"})

        avg = sum(h.get("avg_amount", 0) for h in history) / len(history) if history else 0
        if avg > 0 and txn.get("amount", 0) > avg * 5:
            risk_score += 25
            anomalies += 1
            signals.append({"signal": "amount_anomaly", "weight": 0.25, "description": f"Amount Rs {txn.get('amount',0):,.0f} is {txn.get('amount',0)/avg:.1f}x average"})

        if anomalies >= 3:
            risk_score += 20
            signals.append({"signal": "multi_factor_anomaly", "weight": 0.2, "description": "Multiple behavioral factors changed simultaneously"})

        if risk_score < 35:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.ACCOUNT_TAKEOVER,
            confidence=min(1.0, risk_score / 100),
            severity="CRITICAL",
            signals=signals,
            explanation="Sudden change in device, location, timing, and amount suggests the account may be compromised. Multiple behavioral factors changed simultaneously.",
            is_customer_risk=True,
            recommended_action="HOLD",
        )

    def detect_card_testing(self, recent: list, current: dict) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        same_payment = [t for t in recent if t.get("payment_method") == current.get("payment_method")
                        and t.get("customer_id") == current.get("customer_id")]

        small_txns = [t for t in same_payment if t.get("amount", 0) < 100]
        if len(small_txns) >= 2:
            risk_score += 40
            signals.append({"signal": "small_value_testing", "weight": 0.4, "description": f"{len(small_txns)} small-value transactions detected"})

        large_after_small = [t for t in same_payment if t.get("amount", 0) > 10000]
        if small_txns and large_after_small:
            risk_score += 30
            signals.append({"signal": "escalation_pattern", "weight": 0.3, "description": "Small test transactions followed by large purchase attempt"})

        unique_merchants = set(t.get("merchant_name") for t in same_payment if t.get("merchant_name"))
        if len(unique_merchants) >= 3 and len(same_payment) <= 5:
            risk_score += 20
            signals.append({"signal": "multi_merchant", "weight": 0.2, "description": f"Transactions across {len(unique_merchants)} different merchants"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.CARD_TESTING,
            confidence=min(1.0, risk_score / 100),
            severity="HIGH",
            signals=signals,
            explanation="Pattern of small-value test transactions suggests stolen card details being validated before a large fraudulent purchase.",
            is_customer_risk=True,
            recommended_action="REVIEW",
        )

    def detect_refund_abuse(self, txn: dict, history: list) -> Optional[FraudPatternResult]:
        risk_score = 0
        signals = []

        prev_refunds = sum(1 for h in history if h.get("has_refund", False))
        if prev_refunds >= 2:
            risk_score += 25
            signals.append({"signal": "repeat_refund_history", "weight": 0.25, "description": f"Customer has {prev_refunds} previous refund/chargeback claims"})

        if txn.get("dispute_filed") and txn.get("delivery_confirmed"):
            risk_score += 40
            signals.append({"signal": "post_delivery_dispute", "weight": 0.4, "description": "Dispute filed after delivery was confirmed"})

        if risk_score < 30:
            return None

        return FraudPatternResult(
            pattern_type=FraudPatternType.REFUND_ABUSE,
            confidence=min(1.0, risk_score / 100),
            severity="MEDIUM",
            signals=signals,
            explanation="Pattern of refund/chargeback claims suggests potential friendly fraud or refund abuse behavior.",
            is_customer_risk=True,
            recommended_action="REVIEW",
        )
