# RiskGuard AI

AI Risk Investigation & Adaptive Fraud Detection System for the Razorpay Buildathon - AI Risk Manager Track.

## Overview

RiskGuard AI is a production-style prototype that detects suspicious payment transactions, investigates risk using a grounded AI agent, personalizes risk via behavioral fingerprints, and supports human review with a feedback learning loop.

### Core Differentiators

1. **AI Risk Investigation Agent** - After flagging a transaction, the agent investigates structured signals and produces a grounded investigation report using backend tools (no hallucinated evidence).
2. **Behavioral Risk Fingerprint** - Creates customer-level behavioral baselines and calculates how much new transactions deviate from normal patterns.
3. **Human Feedback Learning Loop** - Captures reviewer decisions, identifies false positives/negatives, monitors model quality, and prepares data for future retraining.

## Architecture

```
riskguard-ai/
├── backend/          # Python FastAPI backend
│   ├── app/
│   │   ├── api/      # REST API endpoints
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic request/response schemas
│   │   ├── services/ # Business logic (risk scoring, behavioral fingerprinting)
│   │   └── agents/   # AI investigation agent with tool access
│   └── requirements.txt
├── ml/               # Machine learning pipeline
│   ├── src/          # Data generation, feature engineering, model training
│   ├── models/       # Saved model artifacts
│   └── evaluation/   # Model evaluation metrics
├── frontend/         # React + TypeScript + Tailwind CSS
│   └── src/
│       ├── components/  # Shared UI components
│       ├── pages/       # Page components
│       ├── services/    # API client
│       └── types/       # TypeScript type definitions
├── scripts/          # Setup and training scripts
└── docs/             # Documentation
```

## Tech Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Recharts, React Router
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic
- **ML**: scikit-learn, Random Forest, SHAP, XGBoost (optional)
- **Database**: SQLite (demo) / PostgreSQL (production)
- **LLM**: Provider-agnostic adapter (OpenAI-compatible, deterministic fallback)

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### 2. Train ML Model

```bash
cd ..
python scripts/train_model.py
```

### 3. Seed Database

```bash
python scripts/seed_database.py
```

### 4. Start Backend

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 6. Open Browser

Navigate to `http://localhost:5173`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/transactions/` | GET | List transactions |
| `/api/transactions/{id}` | GET | Get transaction detail |
| `/api/transactions/` | POST | Create and score transaction |
| `/api/transactions/{id}/score` | POST | Re-score transaction |
| `/api/risk/scores` | GET | List risk assessments |
| `/api/risk/distribution` | GET | Risk tier distribution |
| `/api/investigations/` | GET | List investigations |
| `/api/investigations/{id}` | GET | Get investigation detail |
| `/api/investigations/{txn_id}/investigate` | POST | Run AI investigation |
| `/api/reviews/` | GET | List reviews |
| `/api/reviews/` | POST | Submit human decision |
| `/api/reviews/pending-count` | GET | Pending review count |
| `/api/analytics/overview` | GET | Dashboard analytics |
| `/api/analytics/model-performance` | GET | ML model metrics |
| `/api/analytics/risk-trends` | GET | Risk score trends |
| `/api/analytics/audit-trail` | GET | Audit logs |
| `/api/feedback/summary` | GET | Feedback metrics |
| `/api/feedback/errors` | GET | Error patterns |
| `/api/feedback/export` | GET | Export feedback data |

## Risk Tiers

| Score Range | Tier | Action |
|-------------|------|--------|
| 0-30 | LOW | ALLOW |
| 31-60 | MEDIUM | VERIFY |
| 61-80 | HIGH | REVIEW |
| 81-100 | CRITICAL | HOLD |

## ML Model Performance

The system trains three baseline models and selects the best:
- Logistic Regression (interpretable baseline)
- Random Forest (selected best model)
- Gradient Boosting

Key metrics on test set:
- **Precision**: 97.8%
- **Recall**: 100%
- **F1 Score**: 98.9%
- **PR-AUC**: 1.0

## Demo Scenarios

1. **Normal transaction** → Low risk → Auto-allow
2. **Unusual amount** → Behavioral deviation triggered → Investigation
3. **High-risk transaction** → AI agent retrieves evidence → Recommends review
4. **False positive** → Human marks legitimate → Shows in error analytics
5. **Confirmed fraud** → Feedback recorded → Audit trail

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=sqlite:///./riskguard.db
LLM_PROVIDER=openai          # Optional: for LLM-powered investigations
LLM_API_KEY=                 # Optional: your API key
LLM_MODEL=gpt-4
FP_COST_PER_INCIDENT=50.0    # Simulated cost per false positive
FN_COST_PER_INCIDENT=500.0   # Simulated cost per false negative
```

## License

Built for Razorpay Buildathon. Educational use only.
