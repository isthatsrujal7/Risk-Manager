from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.models.database import Base


def gen_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    account_created = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    risk_tier = Column(String, default="LOW")

    transactions = relationship("Transaction", back_populates="customer")
    behavioral_profile = relationship("BehavioralProfile", back_populates="customer", uselist=False)
    investigations = relationship("Investigation", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    payment_method = Column(String, nullable=True)
    merchant_category = Column(String, nullable=True)
    merchant_name = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    location_city = Column(String, nullable=True)
    location_country = Column(String, default="IN")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_fraud = Column(Boolean, default=False)
    payment_status = Column(String, default="completed")
    settlement_status = Column(String, default="completed")
    display_status = Column(String, default="completed")
    actual_status = Column(String, default="completed")
    bank_callback_status = Column(String, nullable=True)
    gateway_status = Column(String, nullable=True)
    bank_ref_number = Column(String, nullable=True)
    reversal_count = Column(Integer, default=0)
    merchant_id = Column(String, nullable=True)

    customer = relationship("Customer", back_populates="transactions")
    risk_assessment = relationship("RiskAssessment", back_populates="transaction", uselist=False)
    investigations = relationship("Investigation", back_populates="transaction")


class BehavioralProfile(Base):
    __tablename__ = "behavioral_profiles"

    customer_id = Column(String, ForeignKey("customers.customer_id"), primary_key=True)
    avg_transaction_amount = Column(Float, default=0.0)
    std_transaction_amount = Column(Float, default=0.0)
    median_transaction_amount = Column(Float, default=0.0)
    max_transaction_amount = Column(Float, default=0.0)
    total_transactions = Column(Integer, default=0)
    avg_transactions_per_day = Column(Float, default=0.0)
    common_hours = Column(JSON, default=list)
    common_categories = Column(JSON, default=dict)
    common_devices = Column(JSON, default=list)
    common_locations = Column(JSON, default=list)
    avg_amount_last_5 = Column(Float, default=0.0)
    avg_amount_last_15 = Column(Float, default=0.0)
    avg_amount_last_60 = Column(Float, default=0.0)
    tx_count_last_5 = Column(Integer, default=0)
    tx_count_last_15 = Column(Integer, default=0)
    tx_count_last_60 = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="behavioral_profile")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_risk_assessment_transaction"),
    )

    assessment_id = Column(String, primary_key=True, default=lambda: gen_id("RA-"))
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False)
    ml_risk_score = Column(Float, default=0.0)
    ml_prediction = Column(String, default="legitimate")
    ml_confidence = Column(Float, default=0.0)
    behavioral_deviation_score = Column(Float, default=0.0)
    final_risk_score = Column(Float, default=0.0)
    risk_tier = Column(String, default="LOW")
    recommended_action = Column(String, default="ALLOW")
    handling_user = Column(String, default="AI")
    hitl_band = Column(String, default="AI_AUTOPILOT")
    needs_alert = Column(Boolean, default=False)
    top_signals = Column(JSON, default=list)
    feature_contributions = Column(JSON, default=dict)
    model_version = Column(String, default="v1.0")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    transaction = relationship("Transaction", back_populates="risk_assessment")
    investigation = relationship("Investigation", back_populates="risk_assessment", uselist=False)


class Investigation(Base):
    __tablename__ = "investigations"

    investigation_id = Column(String, primary_key=True, default=lambda: gen_id("INV-"))
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    risk_assessment_id = Column(String, ForeignKey("risk_assessments.assessment_id"), nullable=True)
    summary = Column(Text, default="")
    evidence = Column(JSON, default=list)
    contributing_factors = Column(JSON, default=list)
    behavioral_anomalies = Column(JSON, default=list)
    related_activity = Column(JSON, default=list)
    uncertainty = Column(Text, default="")
    recommended_action = Column(String, default="REVIEW")
    explanation = Column(Text, default="")
    agent_model_used = Column(String, default="deterministic")
    is_llm_generated = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    transaction = relationship("Transaction", back_populates="investigations")
    customer = relationship("Customer", back_populates="investigations")
    risk_assessment = relationship("RiskAssessment", back_populates="investigation")
    review = relationship("Review", back_populates="investigation", uselist=False)


class Review(Base):
    __tablename__ = "reviews"

    review_id = Column(String, primary_key=True, default=lambda: gen_id("REV-"))
    investigation_id = Column(String, ForeignKey("investigations.investigation_id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False)
    ai_recommendation = Column(String, default="")
    human_decision = Column(String, nullable=True)
    reviewer_note = Column(Text, default="")
    reviewer_name = Column(String, default="system")
    decision_timestamp = Column(DateTime, nullable=True)
    outcome = Column(String, nullable=True)
    is_false_positive = Column(Boolean, default=False)
    is_false_negative = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    investigation = relationship("Investigation", back_populates="review")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True, default=lambda: gen_id("AUD-"))
    transaction_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, default=dict)
    model_version = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FraudPatternTrack(Base):
    __tablename__ = "fraud_pattern_tracks"

    pattern_id = Column(String, primary_key=True, default=lambda: gen_id("FP-"))
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    pattern_type = Column(String, nullable=False)
    pattern_name = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    severity = Column(String, default="MEDIUM")
    signals = Column(JSON, default=list)
    explanation = Column(Text, default="")
    is_merchant_risk = Column(Boolean, default=False)
    is_customer_risk = Column(Boolean, default=False)
    recommended_action = Column(String, default="REVIEW")
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MerchantRiskProfile(Base):
    __tablename__ = "merchant_risk_profiles"

    merchant_id = Column(String, primary_key=True)
    merchant_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    total_transactions = Column(Integer, default=0)
    total_amount = Column(Float, default=0.0)
    flagged_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    settlement_failure_count = Column(Integer, default=0)
    reverse_count = Column(Integer, default=0)
    avg_risk_score = Column(Float, default=0.0)
    max_risk_score = Column(Float, default=0.0)
    risk_tier = Column(String, default="LOW")
    risk_score = Column(Float, default=0.0)
    pattern_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True, default=lambda: gen_id("AL-"))
    alert_type = Column(String, default="RISK_ALERT")
    transaction_id = Column(String, nullable=True)
    severity = Column(String, default="CRITICAL")
    source = Column(String, default="hitl")
    title = Column(String, default="")
    message = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    status = Column(String, default="OPEN")       # OPEN / ACKNOWLEDGED / RESOLVED
    assigned_to = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: gen_id("USR-"))
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="viewer")   # viewer / analyst / admin
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
