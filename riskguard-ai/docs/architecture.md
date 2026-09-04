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
- **Feature Pipeline**: Categorical encoding, numeric scaling, feature engineering
- **Fraud Classifier**: Random Forest with class weighting
- **Explainability**: SHAP values for feature contributions

### Behavioral Engine
- Customer transaction history analysis
- Baseline profile (amount, timing, devices, locations, categories)
- Deviation scoring with configurable weights

### AI Investigation Agent
- Uses backend tools to retrieve structured data (no hallucinated evidence)
- Synthesizes evidence into risk summary, contributing factors, and recommendations
- Deterministic fallback when LLM is unavailable
- Provider-agnostic LLM adapter

### Risk Policy Engine
- Configurable tier thresholds and action mappings
- Weighted scoring (ML + behavioral)

### Human Review
- Queue-based workflow
- Decision tracking (approve/reject/escalate/uncertain)
- AI recommendation vs human decision distinction

### Feedback Loop
- Prediction vs outcome tracking
- False positive/negative identification
- Error pattern analysis
- Export pipeline for retraining
