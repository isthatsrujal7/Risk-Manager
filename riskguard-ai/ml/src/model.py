import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score, confusion_matrix,
    precision_recall_curve, auc, classification_report
)
import joblib
import os
import json
from datetime import datetime

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


class FraudModel:
    def __init__(self, model_type="random_forest", model_version="v1.0"):
        self.model_type = model_type
        self.model_version = model_version
        self.model = None
        self.model_name_map = {
            "logistic_regression": "Logistic Regression",
            "random_forest": "Random Forest",
            "gradient_boosting": "Gradient Boosting",
            "xgboost": "XGBoost",
        }

    def _create_model(self):
        if self.model_type == "logistic_regression":
            return LogisticRegression(
                max_iter=1000, class_weight="balanced", random_state=42
            )
        elif self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=200, max_depth=12, class_weight="balanced",
                random_state=42, n_jobs=-1
            )
        elif self.model_type == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42
            )
        elif self.model_type == "xgboost" and HAS_XGB:
            return xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                scale_pos_weight=10, use_label_encoder=False,
                eval_metric="logloss", random_state=42
            )
        else:
            return RandomForestClassifier(
                n_estimators=200, max_depth=12, class_weight="balanced",
                random_state=42, n_jobs=-1
            )

    def train(self, X_train, y_train, X_val=None, y_val=None):
        self.model = self._create_model()
        self.model.fit(X_train, y_train)

        metrics = {"train": self.evaluate(X_train, y_train)}
        if X_val is not None and y_val is not None:
            metrics["val"] = self.evaluate(X_val, y_val)

        return metrics

    def predict_proba(self, X):
        if self.model is None:
            raise ValueError("Model not trained yet")
        proba = self.model.predict_proba(X)
        return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]

    def predict(self, X, threshold=0.5):
        proba = self.predict_proba(X)
        return (proba >= threshold).astype(int)

    def evaluate(self, X, y, threshold=0.5):
        proba = self.predict_proba(X)
        y_pred = (proba >= threshold).astype(int)

        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        cm = confusion_matrix(y, y_pred).tolist()

        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
        total = tp + tn + fp + fn
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

        try:
            prec_arr, rec_arr, _ = precision_recall_curve(y, proba)
            pr_auc = auc(rec_arr, prec_arr)
        except Exception:
            pr_auc = 0.0

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "confusion_matrix": cm,
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4),
            "pr_auc": round(pr_auc, 4),
            "true_positives": int(tp),
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "total_samples": int(total),
            "model_type": self.model_name_map.get(self.model_type, self.model_type),
            "model_version": self.model_version,
        }

    def get_shap_values(self, X, feature_names):
        if not HAS_SHAP or self.model is None:
            return {}
        try:
            explainer = shap.TreeExplainer(self.model) if hasattr(self.model, "estimators_") else shap.LinearExplainer(self.model, X)
            shap_values = explainer.shap_values(X)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            mean_abs = np.abs(shap_values).mean(axis=0)
            contributions = dict(zip(feature_names, mean_abs.tolist()))
            sorted_contrib = dict(sorted(contributions.items(), key=lambda x: x[1], reverse=True))
            return sorted_contrib
        except Exception:
            return {}

    def get_prediction_explanation(self, x_single, feature_names):
        if not HAS_SHAP or self.model is None:
            return {}
        try:
            explainer = shap.TreeExplainer(self.model) if hasattr(self.model, "estimators_") else shap.LinearExplainer(self.model, x_single.reshape(1, -1))
            sv = explainer.shap_values(x_single.reshape(1, -1))
            if isinstance(sv, list):
                sv = sv[1]
            sv = sv[0]
            contributions = {}
            for i, fname in enumerate(feature_names):
                contributions[fname] = {
                    "value": float(x_single[i]),
                    "shap_value": float(sv[i]),
                    "direction": "increases_risk" if sv[i] > 0 else "decreases_risk"
                }
            sorted_contrib = dict(sorted(contributions.items(), key=lambda x: abs(x[1]["shap_value"]), reverse=True))
            return sorted_contrib
        except Exception:
            return {}

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({"model": self.model, "model_type": self.model_type, "model_version": self.model_version}, path)

    def load(self, path: str):
        data = joblib.load(path)
        self.model = data["model"]
        self.model_type = data["model_type"]
        self.model_version = data["model_version"]


def train_and_evaluate(data_dict, feature_columns):
    from ml.src.feature_pipeline import FeaturePipeline

    pipeline = FeaturePipeline()
    X_train, cols = pipeline.fit_transform(data_dict["train"])
    y_train = data_dict["train"]["is_fraud"].astype(int).values

    X_val = pipeline.transform(data_dict["val"])
    y_val = data_dict["val"]["is_fraud"].astype(int).values

    X_test = pipeline.transform(data_dict["test"])
    y_test = data_dict["test"]["is_fraud"].astype(int).values

    results = {}
    models = {}

    for mtype in ["logistic_regression", "random_forest", "gradient_boosting"]:
        model = FraudModel(model_type=mtype, model_version=f"v1.0-{mtype}")
        metrics = model.train(X_train, y_train, X_val, y_val)
        test_metrics = model.evaluate(X_test, y_test)
        results[mtype] = {"train": metrics["train"], "val": metrics["val"], "test": test_metrics}
        models[mtype] = model

    best_model_name = max(results, key=lambda k: results[k]["test"]["f1"])
    best_model = models[best_model_name]

    os.makedirs("ml/models", exist_ok=True)
    pipeline.save("ml/models/feature_pipeline.joblib")
    best_model.save("ml/models/fraud_model.joblib")

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    overall_metrics = _clean(dict(results[best_model_name]["test"]))
    overall_metrics["best_model"] = best_model_name
    overall_metrics["all_model_results"] = {k: _clean(dict(v["test"])) for k, v in results.items()}
    overall_metrics["model_version"] = f"v1.0-{best_model_name}"

    with open("ml/models/evaluation_metrics.json", "w") as f:
        json.dump(overall_metrics, f, indent=2)

    shap_contributions = best_model.get_shap_values(X_test, cols)

    return {
        "models": results,
        "best_model": best_model_name,
        "pipeline": pipeline,
        "feature_columns": cols,
        "shap_contributions": shap_contributions,
        "X_test": X_test,
        "y_test": y_test,
    }
