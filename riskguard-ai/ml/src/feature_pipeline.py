import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
import os
import joblib
from datetime import datetime


NUMERIC_FEATURES = [
    "amount", "account_age_days", "customer_avg_amount", "customer_std_amount",
    "hour", "day_of_week", "amount_to_avg_ratio", "is_unusual_hour",
    "is_unusual_amount", "is_new_device", "is_new_city", "is_high_amount"
]

CATEGORICAL_FEATURES = ["payment_method", "merchant_category"]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
    else:
        df["hour"] = 12
        df["day_of_week"] = 3

    if "customer_avg_amount" in df.columns:
        df["amount_to_avg_ratio"] = df["amount"] / (df["customer_avg_amount"] + 1)
    else:
        df["amount_to_avg_ratio"] = 1.0

    df["is_unusual_hour"] = ((df["hour"] < 6) | (df["hour"] > 23)).astype(int)
    if "customer_avg_amount" in df.columns and "customer_std_amount" in df.columns:
        upper = df["customer_avg_amount"] + 3 * df["customer_std_amount"]
        df["is_unusual_amount"] = (df["amount"] > upper).astype(int)
    else:
        df["is_unusual_amount"] = (df["amount"] > 50000).astype(int)

    # Preserve caller-provided values (live serving computes these from the real
    # behavioral profile) instead of silently zeroing them. Only default when the
    # column is absent, so training and serving stay on the same feature space.
    # fillna(0) guards feedback-loop rows that were merged from DB records and
    # may not carry these flags on every frame.
    if "is_new_device" in df.columns:
        df["is_new_device"] = df["is_new_device"].fillna(0).astype(int)
    else:
        df["is_new_device"] = 0

    if "is_new_city" in df.columns:
        df["is_new_city"] = df["is_new_city"].fillna(0).astype(int)
    else:
        df["is_new_city"] = 0

    df["is_high_amount"] = (df["amount"] > 100000).astype(int)

    return df


class FeaturePipeline:
    def __init__(self):
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.feature_columns = []

    def fit_transform(self, df: pd.DataFrame):
        df = engineer_features(df)

        for col in CATEGORICAL_FEATURES:
            if col in df.columns:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                self.label_encoders[col] = le

        self.feature_columns = [c for c in NUMERIC_FEATURES + CATEGORICAL_FEATURES if c in df.columns]
        X = df[self.feature_columns].fillna(0)
        X_scaled = self.scaler.fit_transform(X)

        return X_scaled, self.feature_columns

    def transform(self, df: pd.DataFrame):
        df = engineer_features(df)

        for col in CATEGORICAL_FEATURES:
            if col in df.columns and col in self.label_encoders:
                le = self.label_encoders[col]
                df[col] = df[col].astype(str).apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )

        X = df[self.feature_columns].fillna(0)
        X_scaled = self.scaler.transform(X)
        return X_scaled

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            "label_encoders": self.label_encoders,
            "scaler": self.scaler,
            "feature_columns": self.feature_columns,
        }, path)

    def load(self, path: str):
        data = joblib.load(path)
        self.label_encoders = data["label_encoders"]
        self.scaler = data["scaler"]
        self.feature_columns = data["feature_columns"]
