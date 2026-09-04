export interface Transaction {
  transaction_id: string;
  customer_id: string;
  amount: number;
  currency: string;
  payment_method: string | null;
  merchant_category: string | null;
  merchant_name: string | null;
  device_id: string | null;
  ip_address: string | null;
  location_city: string | null;
  location_country: string;
  timestamp: string;
  is_fraud: boolean;
}

export interface RiskAssessment {
  assessment_id: string;
  transaction_id: string;
  ml_risk_score: number;
  ml_prediction: string;
  ml_confidence: number;
  behavioral_deviation_score: number;
  final_risk_score: number;
  risk_tier: string;
  recommended_action: string;
  top_signals: Signal[];
  feature_contributions: Record<string, number>;
  model_version: string;
  timestamp: string;
}

export interface Signal {
  signal: string;
  value: number;
  weight: number;
  description: string;
}

export interface Investigation {
  investigation_id: string;
  transaction_id: string;
  customer_id: string;
  risk_assessment_id: string | null;
  summary: string;
  evidence: Evidence[];
  contributing_factors: string[];
  behavioral_anomalies: string[];
  related_activity: RelatedActivity[];
  uncertainty: string;
  recommended_action: string;
  explanation: string;
  agent_model_used: string;
  is_llm_generated: boolean;
  timestamp: string;
  transaction?: Transaction;
  risk_assessment?: {
    final_risk_score: number;
    behavioral_deviation_score: number;
    ml_risk_score: number;
    risk_tier: string;
    top_signals: Signal[];
  };
  review?: Review | null;
}

export interface Evidence {
  type: string;
  value: number | string;
  source: string;
  description: string;
}

export interface RelatedActivity {
  transaction_id: string;
  amount: number;
  category: string;
  timestamp: string;
}

export interface Review {
  review_id: string;
  investigation_id: string;
  transaction_id: string;
  ai_recommendation: string;
  human_decision: string | null;
  reviewer_note: string;
  reviewer_name: string;
  decision_timestamp: string | null;
  outcome: string | null;
  is_false_positive: boolean;
  is_false_negative: boolean;
  created_at: string;
}

export interface AnalyticsOverview {
  total_transactions: number;
  total_assessments: number;
  high_risk_count: number;
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  false_negative_rate: number;
  total_fp_cost: number;
  total_fn_cost: number;
  total_cost: number;
  risk_distribution: Record<string, number>;
  model_version: string;
  fp_count: number;
  fn_count: number;
  tp_count: number;
  tn_count: number;
  actual_fraud: number;
  flagged_suspicious: number;
  fp_cost_per_incident: number;
  fn_cost_per_incident: number;
}

export interface AuditLogEntry {
  log_id: string;
  transaction_id: string | null;
  event_type: string;
  event_data: Record<string, unknown>;
  model_version: string | null;
  timestamp: string;
}

export interface BehavioralProfile {
  customer_id: string;
  avg_transaction_amount: number;
  std_transaction_amount: number;
  median_transaction_amount: number;
  max_transaction_amount: number;
  total_transactions: number;
  avg_transactions_per_day: number;
  common_hours: number[];
  common_categories: Record<string, number>;
  common_devices: string[];
  common_locations: string[];
  avg_amount_last_5: number;
  avg_amount_last_15: number;
  avg_amount_last_60: number;
  tx_count_last_5: number;
  tx_count_last_15: number;
  tx_count_last_60: number;
  last_updated: string;
}

export interface ReviewItem {
  review_id: string;
  investigation_id: string;
  transaction_id: string;
  amount: number;
  customer_id: string;
  ai_recommendation: string;
  human_decision: string | null;
  reviewer_note: string;
  reviewer_name: string;
  outcome: string | null;
  summary: string;
  recommended_action: string;
  timestamp: string;
  decision_timestamp: string | null;
}
