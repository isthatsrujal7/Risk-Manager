# Architecture

## System Overview

RiskGuard AI is a fraud detection platform that combines ML-based risk scoring, behavioral analysis, AI-powered investigation, human review, and feedback learning into a single workflow.

## Data Flow

```
Transaction Input
    ↓
Data Validation & Feature Engineering
    ↓
ML Fraud Classifier (Random Forest)
    ↓
Base Risk Score (0-100)
    ↓
Behavioral Risk Fingerprint Service
    ↓
Behavioral Deviation Score (0-100)
    ↓
Combined Risk Score (70% ML + 30% Behavioral)
    ↓
Risk Tier Assignment (LOW/MEDIUM/HIGH/CRITICAL)
    ↓
┌──────────────────────────────────────────────────────┐
│ LOW: Allow    │ MEDIUM: Verify │ HIGH/CRITICAL:      │
│               │                │ AI Investigation     │
│               │                │ → Grounded Report    │
│               │                │ → Recommendation     │
│               │                │ → Human Review       │
└──────────────────────────────────────────────────────┘
    ↓
Audit Log
    ↓
Outcome Recording → Feedback Analytics → Model Monitoring
```

## Components

### ML Layer
- **Feature Pipeline**: Categorical encoding, numeric scaling, feature engineering. `is_new_device` / `is_new_city` are computed from the customer's real behavioral profile at serving time (`risk_scoring._compute_ml_score`) — the same semantics the training generator emits — closing the train/serve skew found in review.
- **Fraud Classifier**: Random Forest with class weighting (best of three by held-out F1)
- **Explainability**: SHAP values for feature contributions

### Behavioral Engine
- Customer transaction history analysis
- Baseline profile (amount, timing, devices, locations, categories)
- Deviation scoring with configurable weights
- **Contamination-free**: when scoring a transaction, the baseline is rebuilt
  excluding that exact transaction; recency/velocity windows are measured
  against the event's own timestamp, not wall-clock time
  (`backend/app/services/behavioral.py`)

### AI Investigation Agent
- Uses backend tools to retrieve structured data (no hallucinated evidence)
- Synthesizes evidence into risk summary, contributing factors, and recommendations
- **LLM output is schema-validated** (`schemas.InvestigationReport`) before it
  can reach the database; malformed output falls back to the deterministic path
- Deterministic fallback when LLM is unavailable
- Provider-agnostic LLM adapter

### Risk Policy Engine
- HITL bands are a **single source of truth** in `backend/app/risk_policy.py`:
  **0–25 AI_AUTOPILOT**, **25–90 HUMAN_REVIEW**, **90–100 AI_MANAGED_BLOCK**
  (score ≥ BAND_BLOCK_MIN always blocks), consumed by scoring, the cost engine,
  the seed script, `.env.example` and the README.
- **Cost-Aware Decisioning** (`backend/app/services/cost_decision.py`): converts the risk score + amount into an expected-loss economics problem:
  - `expected_loss_allow` = `amount × fraud_loss_rate × p(fraud)` — what we lose if we let it through
  - `expected_loss_flag` = `expected_loss_allow × prevention_rate + friction` — what the review/block costs
  - `break_even_prob` — the fraud probability at which flagging and allowing cost the same
  - Decision = ALLOW / VERIFY / REVIEW / BLOCK by which action minimizes expected loss (BLOCK if score ≥ BAND_BLOCK_MIN, REVIEW if ≥ 60)
- Every assessment persists its `cost_decision` object in `feature_contributions`; the analytics layer re-derives it for historical rows and exposes total expected savings (`cost_saved_total`)

### Honest Evaluation Layer
- `ml/src/evaluate_honest.py` re-scores the chronological test split and produces `ml/models/honest_metrics.json`:
  - leakage audit (train/test ID overlap)
  - point metrics **and** 95% bootstrap confidence intervals
  - both the fixed-0.5 operating point and the **cost-optimal point** (minimizes `FP×₹50 + FN×₹500`)
- Served live by `GET /api/analytics/model-performance`
- Dashboard precision/recall/F1 read **only** from `evaluation_metrics.json`
  (held-out test set); operational counts are reported as DB facts and are
  never used to re-derive classification quality

### Data Realism & the Demo Stream
- `ml/src/data_generator.py`: 70% opportunistic fraud (loud), 27% sophisticated (subtle learnable signals), 3% silent mule (mimics the customer), + ~5% legit "novel" behavior (travel/midnight/new device/megabuy) that billable FPs come from
- Chronological split in the generator (train → val → test by timestamp) so evaluation cannot leak future behavior into the past
- `scripts/seed_database.py` stores the **held-out test window** (newest 20%,
  which the model never trained on) and scores it with the exact live-service
  semantics — the demo reproduces the model card's numbers instead of grading
  its own homework

### Human Review
- Queue-based workflow
- Decision tracking (approve/reject/escalate/uncertain)
- AI recommendation vs human decision distinction

### Feedback Loop
- Prediction vs outcome tracking
- False positive/negative identification
- Error pattern analysis
- **Candidate-only retraining**: `POST /api/feedback-loop/retrain` stages a
  versioned candidate (the active model is untouched); `POST
  /api/feedback-loop/approve` is the explicit operator gate that promotes it
- Re-scoring a transaction reuses its `assessment_id` (unique constraint) so
  investigations keep their references and the DB never accumulates duplicates
