# Model Card

## Model Details

- **Model Type**: Random Forest Classifier
- **Version**: v1.0-random_forest
- **Framework**: scikit-learn
- **Training Data**: Synthetic fraud dataset (3,500 train, 500 validation, 1,000 test)
- **Features**: 13 features including amount, timing, customer history ratios, categorical encodings

## Performance

| Metric | Value |
|--------|-------|
| Precision | 0.9778 |
| Recall | 1.0000 |
| F1 Score | 0.9888 |
| PR-AUC | 1.0000 |
| False Positive Rate | 0.001 |
| False Negative Rate | 0.000 |

### Confusion Matrix

| | Predicted Legit | Predicted Fraud |
|--|-----------------|-----------------|
| **Actual Legit** | 955 (TN) | 1 (FP) |
| **Actual Fraud** | 0 (FN) | 44 (TP) |

### Model Comparison

| Model | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Logistic Regression | 0.957 | 1.000 | 0.978 |
| Random Forest | 0.978 | 1.000 | 0.989 |
| Gradient Boosting | 0.978 | 1.000 | 0.989 |

## Intended Use

Fraud detection for payment transactions in a demo/prototype setting.

## Limitations

- Trained on synthetic data, not real payment data
- Behavioral features limited by available transaction history
- Performance may not generalize to real-world distributions
- Class imbalance (5% fraud) handled via class weighting

## Ethical Considerations

- No real customer data used
- Model decisions are explainable via SHAP
- Human review required for high-impact decisions
- False positives represent legitimate transaction disruption
- False negatives represent fraud loss
