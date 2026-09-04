import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.src.data_generator import generate_synthetic_data
from ml.src.feature_pipeline import FeaturePipeline
from ml.src.model import FraudModel, train_and_evaluate
import json


def main():
    print("Generating synthetic fraud dataset...")
    data = generate_synthetic_data(n_customers=200, n_transactions=5000, fraud_rate=0.05, seed=42)

    print(f"  Train: {len(data['train'])} transactions")
    print(f"  Val:   {len(data['val'])} transactions")
    print(f"  Test:  {len(data['test'])} transactions")
    print(f"  Fraud rate (train): {data['train']['is_fraud'].mean():.3f}")

    print("\nTraining and evaluating models...")
    results = train_and_evaluate(data, [])

    print(f"\nBest model: {results['best_model']}")
    print(f"\nTest Metrics ({results['best_model']}):")
    metrics = results["models"][results["best_model"]]["test"]
    for k, v in metrics.items():
        if k != "confusion_matrix":
            print(f"  {k}: {v}")
    print(f"  confusion_matrix: {metrics['confusion_matrix']}")

    print("\nAll model results:")
    for mname, mresult in results["models"].items():
        tm = mresult["test"]
        print(f"  {mname}: P={tm['precision']:.3f} R={tm['recall']:.3f} F1={tm['f1']:.3f}")

    print("\nModel and pipeline saved to ml/models/")
    return results


if __name__ == "__main__":
    main()
