# RiskGuard AI

AI Risk Investigation & Adaptive Fraud Detection System — built for the
**Razorpay AI Buildathon, Track 02: AI Risk Manager**.

> **Submission position**: This is a *defense-only* risk engine. It recommends,
> flags for human review, or blocks a suspicious payment — there is **no**
> offense-capable endpoint (no transaction forgery, no payee alteration, no
> force-clear) anywhere in the codebase. The HITL band `score ≥ 90` always
> blocks; humans decide everything in the 25–90 band.

## The problem we chose

Fraud teams drown in two numbers: **false negatives** (missed chargebacks, the
expensive ones) and **false positives** (good customers nuked by a hair-trigger
model — the expensive-in-a-different-way ones). Most risk demos claim
`Precision 98%` on data that can't survive a 10-second audit. We built an
engine that **reports its own false-positive cost and picks its operating point
by expected-loss economics — not by a fixed 0.5 threshold.**

## What the system does

1. **Cost-aware decisioning** — every transaction is priced: expected loss if
   we *allow*, expected loss if we *flag*, and the break-even fraud
   probability vs. the ₹25 per-review cost (`backend/app/services/cost_decision.py`).
   The engine chooses ALLOW / VERIFY / REVIEW / BLOCK by which action minimizes
   money risk. `score ≥ 90` is always BLOCK and a team alert fires.
2. **AI risk investigation agent** — grounded, tool-using investigation that
   pulls structured evidence from the DB (devices, IPs, merchants, history) —
   no hallucinated evidence.
3. **Behavioral risk fingerprint** — per-customer baselines (amount, device,
   city, hour, category) + deviation scoring.
4. **Honest metrics with FP cost** — leakage audit, chronological split,
   bootstrap 95% CIs, and a cost-optimal operating point (`ml/src/evaluate_honest.py`).
5. **Human-in-the-loop + feedback loop** — reviewers mark transactions,
   the loop detects FP/FN patterns, and one click retrains a model version.

## Honest metrics (do not cherry-pick)

Generated reproducibly by `python scripts/train_model.py`, on a
**chronological split** (train 70% → val 10% → test 20%, no shuffle):

| Operating point | Precision (95% CI) | Recall (95% CI) | FP | FN | Decision cost |
|---|---|---|---|---|---|
| Fixed threshold 0.5 | 100.0% | 74.5% | 0 | 13 | ₹6,500 |
| **Cost-optimal (t≈0.14)** | 62.3% (50.0–73.4%) | 84.3% (73.6–93.0%) | 26 | 8 | **₹5,300** |

The synthetic generator intentionally includes 3% *silent mule* fraud that
mimics the customer's own pattern (86% recall is the honest floor — any claim
of 100% recall on this data is un-auditable). Leakage audit: **0** train/test
ID overlap. Full details: [`docs/model-card.md`](docs/model-card.md).

## Risk tiers (HITL bands, hard-coded)

| Score | HITL band | Action |
|---|---|---|
| 0–25 | AI_AUTOPILOT | ALLOW / auto-process |
| 25–90 | HUMAN_REVIEW | Manual review required (cost-aware: REVIEW/VERIFY/ALLOW) |
| 90–100 | AI_MANAGED_BLOCK | Always BLOCK + alert the risk team |

## Architecture

```
riskguard-ai/
├── backend/                  # Python FastAPI backend
│   ├── app/
│   │   ├── api/              # REST endpoints (transactions, risk, spikes, feedback…)
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # cost_decision, risk_scoring, behavioral, feedback_loop, model_paths
│   │   ├── agents/           # grounded AI investigation agent
│   │   └── risk/             # spike detection (time-anchored z-score)
│   └── requirements.txt
├── ml/
│   ├── src/                  # data_generator (realistic overlap), feature_pipeline, model, evaluate_honest
│   ├── models/               # trained artifacts + honest_metrics.json + evaluation_metrics.json
│   └── evaluation/           # charts/notebooks
├── frontend/                 # React + TypeScript + Tailwind + Recharts
├── scripts/                  # train_model.py, seed_database.py
├── docs/                     # model-card, architecture, demo-script, fixing-it (failure recovery)
└── docker-compose.yml        # one-command stack
```

## Quick Start (two commands, then serve)

```bash
# 1. Train + honest-evaluate the model, then seed the demo database
python scripts/train_model.py && python scripts/seed_database.py

# 2. Start backend (port 8000)
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
# 3. Frontend (port 5173)
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173>. Or run the whole stack with `docker-compose up`.

> Deliberate realism: `*.joblib` models and `*.db` are git-ignored; regenerate
> with the two commands above. `honest_metrics.json` regenerates with every
> training run.

## Key API endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/transactions/` | Score a transaction (returns cost decision) |
| `GET /api/transactions/{id}` | Detail incl. `cost_decision` (expected loss / saving) |
| `GET /api/risk/scores` | Assessments incl. cost decision per score |
| `GET /api/analytics/overview` | Dashboard + expected-loss savings across the book |
| `GET /api/analytics/model-performance` | P/R/F1 + **honest_evaluation** (leakage, CIs, cost point) |
| `GET/POST /api/reviews/` | Human review + feedback labels |
| `POST /api/feedback-loop/retrain` | Retrain a model version on human labels |
| `GET /api/spikes/detect` | Time-anchored fraud spike detection |

## Documentation

- [`docs/model-card.md`](docs/model-card.md) — the honest model card
- [`docs/architecture.md`](docs/architecture.md) — design & flows
- [`docs/demo-script.md`](docs/demo-script.md) — the 5-minute pitch runbook
- [`docs/fixing-it.md`](docs/fixing-it.md) — **failure recovery log** every bug we hit and the guard that now prevents it

## Environment variables (`.env`)

```env
DATABASE_URL=sqlite:///./riskguard.db
LLM_PROVIDER=openai          # optional; deterministic fallback built-in
LLM_API_KEY=
LLM_MODEL=gpt-4
FP_COST_PER_INCIDENT=50.0    # ₹25 review labor + ₹25 CX friction
FN_COST_PER_INCIDENT=500.0   # missed chargeback
```

## License

Built for the Razorpay Buildathon. Educational / demonstration use only;
defense-only by construction.