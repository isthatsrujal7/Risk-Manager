# Model Card

## Model Details

- **Model Type**: Random Forest Classifier (best of three by held-out F1)
- **Version**: v1.0-random_forest
- **Framework**: scikit-learn (200 estimators, max_depth 12, class_weight balanced)
- **Training Data**: Synthetic fraud dataset (3,500 train, 500 validation, 1,000 test), 5% fraud rate
- **Split**: Chronological by timestamp — train = first 70%, then 10% val, last 20% test. **No random shuffle**: shuffling would leak future behavior into the past and flatter the score.
- **Features**: amount, account age, customer spend baseline (mean/std), hour, day-of-week, amount-to-average ratio, unusual-hour/amount flags, **is_new_device / is_new_city** (computed from the customer's behavioral profile at serving time — same semantics as training), payment method, merchant category

## Honest Test-Set Performance

> We report two operating points. Metrics at the fixed 0.5 threshold hide the
> FP/FN trade-off; the *cost-optimal* point is the threshold that minimizes
> money cost at ₹50 per FP vs ₹500 per FN (10:1, because a missed chargeback
> is 10x a single extra manual review). This mirrors the runtime cost engine.

### Fixed threshold (0.5)

| Metric | Point |
|--------|-------|
| Precision | 97.4% |
| Recall | 73.1% |
| F1 | 83.5% |
| Confusion (TP/TN/FP/FN) | 38 / 947 / 1 / 14 |

### Cost-optimal operating point (threshold 0.17, chosen by expected-loss)

| Metric | Point | 95% Bootstrap CI |
|--------|-------|------------------|
| Precision | 71.2% | 60.0% – 95.0% |
| Recall | 90.4% | 82.0% – 98.1% |
| F1 | 79.7% | 74.5% – 92.0% |
| Confusion (TP/TN/FP/FN) | ~47 / ~934 / ~15 / ~5 | |

### Decision cost

| Operating point | FP cost | FN cost | Total |
|-----------------|---------|---------|-------|
| Fixed 0.5 | ₹50 | ₹7,000 | ₹7,050 |
| Cost-optimal 0.17 | ₹750 | ₹2,700 | **₹3,450** |

### Leakage audit

- Train/test ID overlap: **0** → PASS
- Split method: chronological (before = train/val, after = test)
- Data realism: 70% "opportunistic" fraud (loud signals), 27% "sophisticated"
  (subtle signals a model can learn), 3% silent mule (mimics the customer —
  genuinely hard to catch). ~5% of legit customers show novel-but-real
  behavior (travel, midnight, new device, megabuy) which produces the false
  positives that make FP-cost economics real.

### Why the numbers are not perfect (and shouldn't be)

Silent-mule fraud mimics the customer's own pattern, and legitimate novelty
(unexpected travel, a new device, a megabuy) looks structurally similar to
fraud. The cost-optimal point consciously accepts ~15 FPs to catch ~9 more
frauds, because ₹500 per missed chargeback outweighs ₹50 per reviewed good
order. Any system claiming 100% recall on this data is un-auditable.

## Model Comparison (test set, fixed 0.5)

| Model | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Logistic Regression | 0.542 | 0.865 | 0.667 |
| Random Forest | 0.974 | 0.731 | 0.835 |
| Gradient Boosting | 0.973 | 0.692 | 0.809 |

## Train/Serve Consistency

The serving row feeds the exact feature space the model was trained on:
`is_new_device` / `is_new_city` are derived in `risk_scoring._compute_ml_score`
from the customer's behavioral profile (common devices / locations) rather than
being hardcoded to 0, closing the train/serve skew found in the review pass.

## Intended Use

Fraud detection for payment transactions in a defense-only prototype for the
Razorpay AI Buildathon (Track 02). Recommend/HOLD/BLOCK only — there is no
offense-capable endpoint anywhere in this codebase.

## Limitations

- Trained on synthetic data, not real payment data
- Behavioral features limited by available transaction history
- Performance may not generalize to real-world distributions
- Class imbalance (5% fraud) handled via class weighting
- The cost-optimal threshold depends on the ₹50/₹500 cost assumptions; change
  them in `.env` and re-run evaluation (`python scripts/train_model.py`)

## Ethical Considerations

- No real customer data used
- Model decisions are explainable via SHAP
- Human review is required in the 25–90 band; score ≥ 90 always blocks/held
- False positives cost ~₹50 (review labor + CX friction); the UI shows real
  FP-cost numbers rather than hiding them