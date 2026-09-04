from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TransactionCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    payment_method: Optional[str] = None
    merchant_category: Optional[str] = None
    merchant_name: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    location_city: Optional[str] = None
    location_country: str = "IN"
    timestamp: Optional[datetime] = None
    is_fraud: Optional[bool] = False


class TransactionResponse(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: Optional[str]
    merchant_category: Optional[str]
    merchant_name: Optional[str]
    device_id: Optional[str]
    ip_address: Optional[str]
    location_city: Optional[str]
    location_country: str
    timestamp: datetime
    is_fraud: bool

    class Config:
        from_attributes = True


class RiskAssessmentResponse(BaseModel):
    assessment_id: str
    transaction_id: str
    ml_risk_score: float
    ml_prediction: str
    ml_confidence: float
    behavioral_deviation_score: float
    final_risk_score: float
    risk_tier: str
    recommended_action: str
    top_signals: List[Dict[str, Any]]
    feature_contributions: Dict[str, Any]
    model_version: str
    timestamp: datetime

    class Config:
        from_attributes = True


class InvestigationResponse(BaseModel):
    investigation_id: str
    transaction_id: str
    customer_id: str
    risk_assessment_id: Optional[str]
    summary: str
    evidence: List[Dict[str, Any]]
    contributing_factors: List[str]
    behavioral_anomalies: List[str]
    related_activity: List[Dict[str, Any]]
    uncertainty: str
    recommended_action: str
    explanation: str
    agent_model_used: str
    is_llm_generated: bool
    timestamp: datetime

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    investigation_id: str
    transaction_id: str
    human_decision: str
    reviewer_note: str = ""
    reviewer_name: str = "admin"


class ReviewResponse(BaseModel):
    review_id: str
    investigation_id: str
    transaction_id: str
    ai_recommendation: str
    human_decision: Optional[str]
    reviewer_note: str
    reviewer_name: str
    decision_timestamp: Optional[datetime]
    outcome: Optional[str]
    is_false_positive: bool
    is_false_negative: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    transaction_id: str
    outcome: str
    reviewer_name: str = "admin"


class BehavioralProfileResponse(BaseModel):
    customer_id: str
    avg_transaction_amount: float
    std_transaction_amount: float
    median_transaction_amount: float
    max_transaction_amount: float
    total_transactions: int
    avg_transactions_per_day: float
    common_hours: List[int]
    common_categories: Dict[str, float]
    common_devices: List[str]
    common_locations: List[str]
    avg_amount_last_5: float
    avg_amount_last_15: float
    avg_amount_last_60: float
    tx_count_last_5: int
    tx_count_last_15: int
    tx_count_last_60: int
    last_updated: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    log_id: str
    transaction_id: Optional[str]
    event_type: str
    event_data: Dict[str, Any]
    model_version: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class AnalyticsOverview(BaseModel):
    total_transactions: int
    high_risk_count: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    false_negative_rate: float
    total_fp_cost: float
    total_fn_cost: float
    total_cost: float
    risk_distribution: Dict[str, int]
    model_version: str


class RiskScoreRequest(BaseModel):
    transaction_id: str
