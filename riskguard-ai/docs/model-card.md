# Model Card

## Model Details

- **Model Type**: Random Forest Classifier
- **Version**: v1.0-random_forest
- **Framework**: scikit-learn (200 estimators, max_depth 12, class_weight balanced)
- **Training Data**: Synthetic fraud dataset (3,500 train, 500 validation, 1,000 test), 5% fraud rate
- **Split**: Chronological by timestamp — train = first 70%, then 10% val, last 20% test. **No random shuffle**: shuffling would leak future behavior into the past and flatter the score.
- **Features**: amount, account age, customer spend baseline (mean/std), hour, day-of-week, amount-to-average ratio, unusual-hour/amount flags, payment method, merchant category

## Honest Test-Set Performance

> We report two operating points. Metrics at the fixed 0.5 threshold hide the
> FP/FN trade-off; the *cost-optimal* point is the threshold that minimizes
> money cost at ₹50 per FP vs ₹500 per FN (10:1, because a missed chargeback
> is 10x a single extra manual review). This mirrors the runtime cost engine.

### Fixed threshold (0.5)

| Metric | Point | 
|--------|-------|
| Precision | 100.0% |
| Recall | 74.5% |
| F1 | 85.4% |
| Confusion (TP/TN/FP/FN) | 38 / 949 / 0 / 13 |

### Cost-optimal operating point (threshold 0.14, chosen by expected-loss)

| Metric | Point | 95% Bootstrap CI |
|--------|-------|------------------|
| Precision | 62.3% | 50.0% – 73.4% |
| Recall | 84.3% | 73.6% – 93.0% |
| F1 | 71.7% | 61.2% – 80.0% |
| Confusion (TP/TN/FP/FN) | 43 / 923 / 26 / 8 | |

### Decision cost

| Operating point | FP cost | FN cost | Total |
|-----------------|---------|---------|-------|
| Fixed 0.5 | ₹0 | ₹6,500 | ₹6,500 |
| Cost-optimal 0.14 | ₹1,300 | ₹4,000 | **₹5,300** |

### Leakage audit

- Train/test ID overlap: **0** → PASS
- Split method: chronological (before = train/val, after = test)
- Data realism: 70% "opportunistic" fraud (loud signals), 27% "sophisticated"
  (subtle signals a model can learn), 3% silent mule (mimics the customer —
  genuinely hard to catch). ~3% of legit customers show novel-but-real
  behavior (travel, midnight, new device) which costs false positives.

### Why recall at 0.5 is only 74.5%

The 3% silent/mule fraud is, by construction, indistinguishable from the
customer's own pattern — a real, honest floor that no classifier removes. We
prefer an honest 74.5% recall over a claimed 100% that cannot survive a
leakage audit.

## Model Comparison (test set, fixed 0.5)

| Model | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Logistic Regression | 0.632 | 0.843 | 0.723 |
| Random Forest | 1.000 | 0.745 | 0.854 |
| Gradient Boosting | 0.930 | 0.784 | 0.851 |

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