import os
import sys
import json
import requests
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.models import Transaction, Customer, RiskAssessment, Investigation, BehavioralProfile, AuditLog
from app.services.behavioral import BehavioralFingerprintService

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class InvestigationTools:
    def __init__(self, db: Session):
        self.db = db

    def get_transaction(self, transaction_id: str) -> dict:
        txn = self.db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        if not txn:
            return {"error": "Transaction not found"}
        return {
            "transaction_id": txn.transaction_id,
            "customer_id": txn.customer_id,
            "amount": txn.amount,
            "currency": txn.currency,
            "payment_method": txn.payment_method,
            "merchant_category": txn.merchant_category,
            "merchant_name": txn.merchant_name,
            "device_id": txn.device_id,
            "ip_address": txn.ip_address,
            "location_city": txn.location_city,
            "location_country": txn.location_country,
            "timestamp": txn.timestamp.isoformat() if txn.timestamp else None,
            "is_fraud": txn.is_fraud,
        }

    def get_customer_profile(self, customer_id: str) -> dict:
        cust = self.db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not cust:
            return {"error": "Customer not found"}
        return {
            "customer_id": cust.customer_id,
            "name": cust.name,
            "account_created": cust.account_created.isoformat() if cust.account_created else None,
            "risk_tier": cust.risk_tier,
        }

    def get_customer_recent_activity(self, customer_id: str, limit: int = 20) -> dict:
        txns = self.db.query(Transaction).filter(
            Transaction.customer_id == customer_id
        ).order_by(Transaction.timestamp.desc()).limit(limit).all()

        return {
            "customer_id": customer_id,
            "recent_transactions": [
                {
                    "transaction_id": t.transaction_id,
                    "amount": t.amount,
                    "merchant_category": t.merchant_category,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "is_fraud": t.is_fraud,
                }
                for t in txns
            ],
            "total_recent": len(txns),
        }

    def get_behavioral_fingerprint(self, customer_id: str) -> dict:
        profile = self.db.query(BehavioralProfile).filter(
            BehavioralProfile.customer_id == customer_id
        ).first()

        if not profile:
            return {"error": "No behavioral profile found"}

        return {
            "customer_id": customer_id,
            "avg_transaction_amount": profile.avg_transaction_amount,
            "std_transaction_amount": profile.std_transaction_amount,
            "total_transactions": profile.total_transactions,
            "common_hours": profile.common_hours,
            "common_categories": profile.common_categories,
            "common_devices": profile.common_devices,
            "common_locations": profile.common_locations,
            "tx_count_last_5": profile.tx_count_last_5,
            "tx_count_last_15": profile.tx_count_last_15,
            "tx_count_last_60": profile.tx_count_last_60,
        }

    def get_related_transactions(self, transaction_id: str) -> dict:
        txn = self.db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        if not txn:
            return {"error": "Transaction not found"}

        related = self.db.query(Transaction).filter(
            Transaction.customer_id == txn.customer_id,
            Transaction.transaction_id != transaction_id,
        ).order_by(Transaction.timestamp.desc()).limit(10).all()

        return {
            "primary_transaction": transaction_id,
            "related": [
                {
                    "transaction_id": t.transaction_id,
                    "amount": t.amount,
                    "merchant_category": t.merchant_category,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                }
                for t in related
            ],
        }

    def get_model_explanation(self, transaction_id: str) -> dict:
        assessment = self.db.query(RiskAssessment).filter(
            RiskAssessment.transaction_id == transaction_id
        ).first()

        if not assessment:
            return {"error": "No risk assessment found"}

        return {
            "transaction_id": transaction_id,
            "ml_risk_score": assessment.ml_risk_score,
            "ml_prediction": assessment.ml_prediction,
            "ml_confidence": assessment.ml_confidence,
            "feature_contributions": assessment.feature_contributions,
            "model_version": assessment.model_version,
        }

    def get_risk_policy(self) -> dict:
        return {
            "tiers": {
                "LOW": {"range": [0, 30], "action": "ALLOW"},
                "MEDIUM": {"range": [31, 60], "action": "VERIFY"},
                "HIGH": {"range": [61, 80], "action": "REVIEW"},
                "CRITICAL": {"range": [81, 100], "action": "HOLD"},
            },
            "scoring_weights": {"ml_model": 0.7, "behavioral": 0.3},
        }

    def record_reviewer_decision(self, investigation_id: str, decision: str, note: str = "") -> dict:
        inv = self.db.query(Investigation).filter(
            Investigation.investigation_id == investigation_id
        ).first()
        if not inv:
            return {"error": "Investigation not found"}

        from app.models.models import Review
        review = Review(
            investigation_id=investigation_id,
            transaction_id=inv.transaction_id,
            ai_recommendation=inv.recommended_action,
            human_decision=decision,
            reviewer_note=note,
            reviewer_name="agent",
            decision_timestamp=datetime.now(timezone.utc),
        )
        self.db.add(review)
        self.db.commit()

        return {"status": "recorded", "investigation_id": investigation_id, "decision": decision}


class InvestigationAgent:
    def __init__(self, db: Session):
        self.db = db
        self.tools = InvestigationTools(db)

    def investigate(self, transaction_id: str) -> dict:
        txn_data = self.tools.get_transaction(transaction_id)
        if "error" in txn_data:
            return {"error": txn_data["error"]}

        customer_id = txn_data["customer_id"]

        assessment = self.db.query(RiskAssessment).filter(
            RiskAssessment.transaction_id == transaction_id
        ).first()

        customer_profile = self.tools.get_customer_profile(customer_id)
        recent_activity = self.tools.get_customer_recent_activity(customer_id)
        behavioral_fp = self.tools.get_behavioral_fingerprint(customer_id)
        related = self.tools.get_related_transactions(transaction_id)
        model_explanation = self.tools.get_model_explanation(transaction_id)
        risk_policy = self.tools.get_risk_policy()

        investigation_data = {
            "transaction": txn_data,
            "customer_profile": customer_profile,
            "behavioral_fingerprint": behavioral_fp,
            "recent_activity": recent_activity,
            "related_transactions": related,
            "model_explanation": model_explanation,
            "risk_assessment": {
                "final_risk_score": assessment.final_risk_score if assessment else 0,
                "risk_tier": assessment.risk_tier if assessment else "UNKNOWN",
                "behavioral_deviation": assessment.behavioral_deviation_score if assessment else 0,
            } if assessment else None,
        }

        llm_result = self._try_llm_investigation(investigation_data)
        if llm_result:
            return llm_result

        return self._deterministic_investigation(investigation_data)

    def _try_llm_investigation(self, data: dict) -> dict:
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key:
            return None

        provider = os.getenv("LLM_PROVIDER", "openai")
        model = os.getenv("LLM_MODEL", "gpt-4")

        prompt = self._build_investigation_prompt(data)

        try:
            if provider == "openai":
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a fraud investigation AI. Analyze the transaction data provided and return a JSON investigation report. Do NOT invent any facts. Only use the provided data."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    inv_report = json.loads(content)
                    inv_report["is_llm_generated"] = True
                    inv_report["agent_model_used"] = f"{provider}/{model}"
                    return inv_report
        except Exception as e:
            print(f"LLM investigation failed: {e}")

        return None

    def _build_investigation_prompt(self, data: dict) -> str:
        return f"""Investigate this transaction for fraud risk. Use ONLY the data below. Do not invent facts.

Transaction: {json.dumps(data['transaction'], indent=2)}
Risk Assessment: {json.dumps(data.get('risk_assessment', {}), indent=2)}
Customer Profile: {json.dumps(data['customer_profile'], indent=2)}
Behavioral Fingerprint: {json.dumps(data['behavioral_fingerprint'], indent=2)}
Recent Activity: {json.dumps(data['recent_activity'], indent=2)}
Related Transactions: {json.dumps(data['related_transactions'], indent=2)}
Model Explanation: {json.dumps(data['model_explanation'], indent=2)}

Return JSON with keys: summary, evidence (array of objects), contributing_factors (array of strings), behavioral_anomalies (array of strings), related_activity (array of objects), uncertainty (string), recommended_action (string), explanation (string)."""

    def _deterministic_investigation(self, data: dict) -> dict:
        txn = data["transaction"]
        risk = data.get("risk_assessment", {})
        behav = data.get("behavioral_fingerprint", {})
        activity = data.get("recent_activity", {})
        model_exp = data.get("model_explanation", {})

        final_score = risk.get("final_risk_score", 0) if risk else 0
        tier = risk.get("risk_tier", "LOW") if risk else "LOW"
        behav_dev = risk.get("behavioral_deviation", 0) if risk else 0

        evidence = [
            {"type": "risk_score", "value": final_score, "source": "risk_engine", "description": f"Final risk score: {final_score}/100"},
            {"type": "ml_prediction", "value": model_exp.get("ml_prediction", "unknown"), "source": "ml_model", "description": f"ML prediction: {model_exp.get('ml_prediction', 'unknown')} (confidence: {model_exp.get('ml_confidence', 0):.0%})"},
            {"type": "behavioral_deviation", "value": behav_dev, "source": "behavioral_engine", "description": f"Behavioral deviation: {behav_dev}/100"},
        ]

        contributing_factors = []
        if txn["amount"] and behav.get("avg_transaction_amount", 0) > 0:
            ratio = txn["amount"] / (behav["avg_transaction_amount"] + 1)
            if ratio > 2:
                contributing_factors.append(f"Transaction amount ₹{txn['amount']:,.0f} is {ratio:.1f}x the customer's average of ₹{behav['avg_transaction_amount']:,.0f}")

        if txn.get("timestamp"):
            from datetime import datetime as dt
            try:
                ts = dt.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
                if ts.hour < 5 or ts.hour > 23:
                    contributing_factors.append(f"Transaction at unusual hour: {ts.hour}:00")
            except (ValueError, AttributeError):
                pass

        if txn.get("location_country") and txn["location_country"] != "IN":
            contributing_factors.append(f"Foreign location detected: {txn['location_country']}")

        if behav.get("common_devices") and txn.get("device_id") and txn["device_id"] not in behav["common_devices"]:
            contributing_factors.append("New/unrecognized device used for this transaction")

        if behav_dev > 50:
            contributing_factors.append(f"Behavioral deviation score of {behav_dev:.0f} indicates significant departure from normal patterns")

        behavioral_anomalies = []
        if behav.get("avg_transaction_amount") and txn["amount"] > behav["avg_transaction_amount"] * 2:
            behavioral_anomalies.append(f"Amount ₹{txn['amount']:,.0f} far exceeds typical ₹{behav['avg_transaction_amount']:,.0f}")
        if behav.get("common_hours") and txn.get("timestamp"):
            try:
                ts = dt.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
                if ts.hour not in behav["common_hours"]:
                    behavioral_anomalies.append(f"Unusual hour {ts.hour}:00 - customer typically transacts at hours {behav['common_hours']}")
            except (ValueError, AttributeError):
                pass
        if behav.get("common_locations") and txn.get("location_city") and txn["location_city"] not in behav["common_locations"]:
            behavioral_anomalies.append(f"Unusual location: {txn['location_city']}")

        related_txns = activity.get("recent_transactions", [])[:5]
        related_activity = [
            {"transaction_id": rt["transaction_id"], "amount": rt["amount"], "category": rt["merchant_category"], "timestamp": rt["timestamp"]}
            for rt in related_txns
        ]

        uncertainty_parts = []
        if behav.get("total_transactions", 0) < 10:
            uncertainty_parts.append("Limited transaction history for reliable behavioral baseline")
        if final_score > 40 and final_score < 70:
            uncertainty_parts.append("Risk score in moderate range - less certainty in classification")

        uncertainty = "; ".join(uncertainty_parts) if uncertainty_parts else "Evidence relatively clear based on available data"

        if tier == "CRITICAL":
            action = "HOLD"
            summary = f"CRITICAL: Transaction #{txn['transaction_id']} for ₹{txn['amount']:,.0f} flagged with risk score {final_score:.0f}/100. Strong indicators of potential fraud detected."
        elif tier == "HIGH":
            action = "REVIEW"
            summary = f"HIGH RISK: Transaction #{txn['transaction_id']} for ₹{txn['amount']:,.0f} has elevated risk score of {final_score:.0f}/100. Multiple risk factors identified."
        elif tier == "MEDIUM":
            action = "VERIFY"
            summary = f"MEDIUM RISK: Transaction #{txn['transaction_id']} for ₹{txn['amount']:,.0f} shows moderate risk indicators (score: {final_score:.0f}/100)."
        else:
            action = "ALLOW"
            summary = f"LOW RISK: Transaction #{txn['transaction_id']} for ₹{txn['amount']:,.0f} appears within normal parameters (score: {final_score:.0f}/100)."

        explanation_parts = [
            f"Risk analysis performed using {model_exp.get('model_version', 'unknown')} model.",
            f"ML model score: {model_exp.get('ml_risk_score', 0):.0f}/100.",
            f"Behavioral deviation: {behav_dev:.0f}/100.",
            f"Combined final score: {final_score:.0f}/100.",
        ]
        if contributing_factors:
            explanation_parts.append(f"Key factors: {'; '.join(contributing_factors[:3])}.")

        return {
            "summary": summary,
            "evidence": evidence,
            "contributing_factors": contributing_factors,
            "behavioral_anomalies": behavioral_anomalies,
            "related_activity": related_activity,
            "uncertainty": uncertainty,
            "recommended_action": action,
            "explanation": " ".join(explanation_parts),
            "is_llm_generated": False,
            "agent_model_used": "deterministic",
        }
