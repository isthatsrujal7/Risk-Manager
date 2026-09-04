import os
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.models import Transaction, RiskAssessment, BehavioralProfile
from app.services.behavioral import BehavioralFingerprintService
from app.services.cost_decision import cost_decision_dict
from app.services import model_paths
from app import risk_policy

MODEL_VERSION = "v1.0-rf"
_model = None
_pipeline = None


def _load_model():
    global _model, _pipeline
    if _model is not None:
        return
    _load_model_from_disk()


def reload_model_cache():
    """Drop the in-process model/pipeline so the next call reloads from disk."""
    global _model, _pipeline
    _model = None
    _pipeline = None
    _load_model_from_disk()


def _load_model_from_disk():
    global _model, _pipeline
    try:
        from ml.src.model import FraudModel
        from ml.src.feature_pipeline import FeaturePipeline

        model_path = model_paths.model_path("fraud_model.joblib")
        pipeline_path = model_paths.model_path("feature_pipeline.joblib")

        if os.path.exists(model_path) and os.path.exists(pipeline_path):
            _model = FraudModel()
            _model.load(model_path)
            _pipeline = FeaturePipeline()
            _pipeline.load(pipeline_path)
        else:
            _model = FraudModel(model_type="random_forest")
            _pipeline = None
    except Exception as e:
        print(f"Warning: Could not load ML model: {e}")
        _model = None
        _pipeline = None


class RiskScoringService:
    def __init__(self, db: Session):
        self.db = db
        self.behavioral_service = BehavioralFingerprintService(db)

    def score_transaction(self, transaction: Transaction) -> RiskAssessment:
        _load_model()

        # Build the behavioral baseline WITHOUT the transaction being scored
        # (contamination fix) and measure recency windows against the event's own
        # timestamp so re-scoring and backfills are deterministic.
        baseline = self.behavioral_service.update_profile(
            transaction.customer_id,
            exclude_transaction_id=transaction.transaction_id,
            reference_ts=transaction.timestamp,
        )
        ml_score = self._compute_ml_score(transaction, baseline)
        behavioral_deviation = self.behavioral_service.calculate_deviation(transaction, baseline)

        final_score = 0.7 * ml_score + 0.3 * behavioral_deviation
        final_score = min(100, max(0, final_score))

        risk_tier = risk_policy.risk_tier(final_score)
        needs_alert = final_score >= risk_policy.BAND_BLOCK_MIN

        top_signals = self._get_top_signals(transaction, ml_score, behavioral_deviation, baseline)
        feature_contributions = self._get_feature_contributions(transaction, baseline)

        cost = cost_decision_dict(transaction.amount or 0, final_score)
        cost_action = cost["decision"]
        # Cost-aware decision refines the fixed-tier action but never overrides
        # the mandatory HITL block band (score >= BAND_BLOCK_MIN).
        if final_score >= risk_policy.BAND_BLOCK_MIN:
            cost_action = "BLOCK"
        handling_user = self._get_handling_user(risk_tier)

        # Re-scoring a transaction must not create duplicate assessments; reuse
        # the existing assessment_id so investigations keep their reference.
        existing = self.db.query(RiskAssessment).filter(
            RiskAssessment.transaction_id == transaction.transaction_id
        ).first()
        reused_id = existing.assessment_id if existing else None
        if existing:
            self.db.delete(existing)
            self.db.flush()

        assessment = RiskAssessment(
            transaction_id=transaction.transaction_id,
            ml_risk_score=round(ml_score, 2),
            ml_prediction="suspicious" if ml_score > 50 else "legitimate",
            ml_confidence=round(abs(ml_score - 50) / 50, 2),
            behavioral_deviation_score=round(behavioral_deviation, 2),
            final_risk_score=round(final_score, 2),
            risk_tier=risk_tier,
            recommended_action=cost_action,
            handling_user=handling_user,
            hitl_band=risk_policy.hitl_band(final_score),
            needs_alert=needs_alert,
            top_signals=top_signals,
            feature_contributions={**feature_contributions, "cost_decision": cost},
            model_version=MODEL_VERSION,
        )
        if reused_id:
            assessment.assessment_id = reused_id

        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)

        self._log_audit(transaction.transaction_id, "risk_scored", {
            "ml_score": ml_score,
            "behavioral_deviation": behavioral_deviation,
            "final_score": final_score,
            "risk_tier": risk_tier,
            "recommended_action": cost_action,
            "handled_by": handling_user,
            "needs_alert": needs_alert,
            "hitl_band": risk_policy.hitl_band(final_score),
            "cost_decision": cost,
        })

        if needs_alert:
            self._raise_risk_alert(transaction, assessment)
        elif risk_tier == "LOW":
            self._log_audit(transaction.transaction_id, "auto_allowed", {
                "handled_by": "ai",
                "reason": "Low risk score below autopilot ceiling, auto-processed without human review",
            })
        elif risk_tier in ("MEDIUM", "HIGH"):
            self._send_for_human_review(transaction, assessment)

        self._broadcast_live(transaction, assessment)

        # Fold the newly scored transaction into the profile now that it is no
        # longer the event under evaluation.
        self.behavioral_service.update_profile(transaction.customer_id)

        return assessment

    def _broadcast_live(self, transaction: Transaction, assessment: RiskAssessment):
        try:
            from app.services.live_feed import broadcast
            broadcast({
                "type": "new_assessment",
                "data": {
                    "transaction_id": transaction.transaction_id,
                    "customer_id": transaction.customer_id,
                    "amount": transaction.amount,
                    "final_risk_score": assessment.final_risk_score,
                    "risk_tier": assessment.risk_tier,
                    "recommended_action": assessment.recommended_action,
                    "hitl_band": assessment.hitl_band,
                    "cost_decision": (assessment.feature_contributions or {}).get("cost_decision", {}),
                    "timestamp": assessment.timestamp.isoformat() if assessment.timestamp else None,
                },
            })
        except Exception as e:
            print(f"Live feed broadcast failed: {e}")

    def _get_hitl_band(self, score: float) -> str:
        return risk_policy.hitl_band(score)

    def _raise_risk_alert(self, transaction: Transaction, assessment: RiskAssessment):
        """Alert the human risk team for block-band scores while AI auto-blocks."""
        from app.models.models import AuditLog
        alert = AuditLog(
            transaction_id=transaction.transaction_id,
            event_type="risk_team_alert",
            event_data={
                "severity": "CRITICAL",
                "final_risk_score": assessment.final_risk_score,
                "ai_action": "TRANSACTION_BLOCKED_AND_HELD",
                "alert_message": f"CRITICAL ALERT: Transaction {transaction.transaction_id} scored {assessment.final_risk_score:.0f}/100. AI has automatically blocked and held this transaction. Human risk team review recommended IMMEDIATELY.",
                "risk_tier": assessment.risk_tier,
                "recommended_action": assessment.recommended_action,
            },
            model_version=MODEL_VERSION,
        )
        self.db.add(alert)
        self.db.commit()

        self._log_audit(transaction.transaction_id, "ai_auto_held", {
            "reason": f"Score >= {risk_policy.BAND_BLOCK_MIN}. AI blocked transaction and alerted risk team.",
        })

        try:
            from app.services.notifications import create_alert
            create_alert(
                self.db,
                alert_type="CRITICAL_TRANSACTION",
                transaction_id=transaction.transaction_id,
                severity="CRITICAL",
                source="hitl",
                title=f"Critical transaction {transaction.transaction_id} blocked & held",
                message=(
                    f"Transaction {transaction.transaction_id} scored "
                    f"{assessment.final_risk_score:.0f}/100 (CRITICAL). AI has automatically "
                    f"blocked and held this transaction. Human risk team review recommended "
                    f"immediately."
                ),
                metadata={
                    "final_risk_score": assessment.final_risk_score,
                    "risk_tier": assessment.risk_tier,
                    "recommended_action": assessment.recommended_action,
                    "ai_action": "TRANSACTION_BLOCKED_AND_HELD",
                },
            )
        except Exception as e:
            print(f"Alert creation failed: {e}")

    def _send_for_human_review(self, transaction: Transaction, assessment: RiskAssessment):
        """Queue human-review-band transactions for human review."""
        from app.models.models import AuditLog
        queue_entry = AuditLog(
            transaction_id=transaction.transaction_id,
            event_type="sent_for_human_review",
            event_data={
                "final_risk_score": assessment.final_risk_score,
                "risk_tier": assessment.risk_tier,
                "why": "Score in human-review band. AI recommends action but human judgment required.",
                "ai_recommendation": assessment.recommended_action,
            },
            model_version=MODEL_VERSION,
        )
        self.db.add(queue_entry)
        self.db.commit()

        return assessment

    def _compute_ml_score(self, transaction: Transaction, profile: BehavioralProfile = None) -> float:
        if _model is None or _pipeline is None:
            return self._heuristic_score(transaction)

        try:
            avg_amt = profile.avg_transaction_amount if profile and profile.avg_transaction_amount else (transaction.amount or 1000)
            std_amt = profile.std_transaction_amount if profile and profile.std_transaction_amount else (avg_amt * 0.4)
            common_devices = set(profile.common_devices or []) if profile else set()
            common_locations = set(profile.common_locations or []) if profile else set()

            row = pd.DataFrame([{
                "transaction_id": transaction.transaction_id,
                "customer_id": transaction.customer_id,
                "amount": transaction.amount,
                "currency": transaction.currency or "INR",
                "payment_method": transaction.payment_method or "unknown",
                "merchant_category": transaction.merchant_category or "unknown",
                "merchant_name": transaction.merchant_name or "unknown",
                "device_id": transaction.device_id or "unknown",
                "ip_address": transaction.ip_address or "0.0.0.0",
                "location_city": transaction.location_city or "Unknown",
                "location_country": transaction.location_country or "IN",
                "timestamp": transaction.timestamp or datetime.now(timezone.utc),
                "is_fraud": False,
                "account_age_days": 180,
                "customer_avg_amount": avg_amt,
                "customer_std_amount": std_amt,
                # Real behavioral features instead of hardcoded false values, so
                # serving uses the same feature space as training.
                "is_new_device": int(transaction.device_id not in common_devices) if transaction.device_id else 0,
                "is_new_city": int(transaction.location_city not in common_locations) if transaction.location_city else 0,
            }])
            X = _pipeline.transform(row)
            proba = _model.predict_proba(X)
            return float(proba[0]) * 100
        except Exception as e:
            print(f"ML scoring failed, using heuristic: {e}")
            return self._heuristic_score(transaction)

    def _heuristic_score(self, transaction: Transaction) -> float:
        score = 10
        if transaction.amount > 50000:
            score += 30
        elif transaction.amount > 20000:
            score += 15
        elif transaction.amount > 10000:
            score += 5

        if transaction.timestamp:
            hour = transaction.timestamp.hour
            if hour < 5 or hour > 23:
                score += 20

        if transaction.device_id and transaction.device_id.startswith("DEV-1"):
            score += 10

        if transaction.location_country and transaction.location_country != "IN":
            score += 25

        if transaction.payment_method in ("credit_card", "debit_card"):
            if transaction.amount > 30000:
                score += 15

        return min(100, score)

    def _get_risk_tier(self, score: float) -> str:
        return risk_policy.risk_tier(score)

    def _get_recommended_action(self, tier: str) -> str:
        actions = {"LOW": "ALLOW", "MEDIUM": "VERIFY", "HIGH": "REVIEW", "CRITICAL": "HOLD"}
        return actions.get(tier, "ALLOW")

    def _get_handling_user(self, tier: str) -> str:
        if tier == "LOW":
            return "AI"
        elif tier == "CRITICAL":
            return "AI + HUMAN ALERT"
        return "HUMAN REVIEW"

    def _get_top_signals(self, txn, ml_score, behav_score, profile) -> list:
        signals = []
        if profile and profile.avg_transaction_amount > 0:
            ratio = txn.amount / (profile.avg_transaction_amount + 1)
            if ratio > 2:
                signals.append({"signal": "amount_above_average", "value": round(ratio, 2), "weight": 0.35, "description": f"Amount is {ratio:.1f}x average"})

        if txn.timestamp and txn.timestamp.hour < 5:
            signals.append({"signal": "unusual_hour", "value": txn.timestamp.hour, "weight": 0.2, "description": f"Transaction at {txn.timestamp.hour}:00"})

        if txn.location_country and txn.location_country != "IN":
            signals.append({"signal": "foreign_location", "value": txn.location_country, "weight": 0.25, "description": f"Foreign location: {txn.location_country}"})

        if profile and profile.common_devices and txn.device_id and txn.device_id not in profile.common_devices:
            signals.append({"signal": "new_device", "value": txn.device_id, "weight": 0.15, "description": "New device detected"})

        if ml_score > 60:
            signals.append({"signal": "ml_high_risk", "value": round(ml_score, 2), "weight": 0.3, "description": f"ML risk score: {ml_score:.0f}/100"})

        if behav_score > 60:
            signals.append({"signal": "behavioral_anomaly", "value": round(behav_score, 2), "weight": 0.25, "description": f"Behavioral deviation: {behav_score:.0f}/100"})

        signals.sort(key=lambda s: s.get("weight", 0), reverse=True)
        return signals[:5]

    def _get_feature_contributions(self, txn, profile) -> dict:
        contributions = {"amount": 0.0, "timing": 0.0, "device": 0.0, "location": 0.0, "category": 0.0, "velocity": 0.0}
        if profile and profile.avg_transaction_amount > 0:
            contributions["amount"] = min(1.0, txn.amount / (profile.avg_transaction_amount * 3))
        if txn.timestamp:
            contributions["timing"] = 0.8 if txn.timestamp.hour < 5 else 0.2
        if profile and txn.device_id and txn.device_id not in profile.common_devices:
            contributions["device"] = 0.7
        if txn.location_country and txn.location_country != "IN":
            contributions["location"] = 0.9
        return contributions

    def _log_audit(self, txn_id, event_type, event_data):
        from app.models.models import AuditLog
        audit = AuditLog(
            transaction_id=txn_id,
            event_type=event_type,
            event_data=event_data,
            model_version=MODEL_VERSION,
        )
        self.db.add(audit)
        self.db.commit()