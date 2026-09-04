import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.models import Transaction, BehavioralProfile, Customer


class BehavioralFingerprintService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_profile(self, customer_id: str) -> BehavioralProfile:
        profile = self.db.query(BehavioralProfile).filter(
            BehavioralProfile.customer_id == customer_id
        ).first()

        if profile is None:
            profile = BehavioralProfile(customer_id=customer_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    def update_profile(self, customer_id: str, exclude_transaction_id: str = None, reference_ts=None) -> BehavioralProfile:
        """Recompute the customer's behavioral baseline from transaction history.

        exclude_transaction_id: when scoring a transaction, pass its id so the
            baseline never includes the exact event being scored (contamination
            fix). Once scoring finishes, call update_profile() again (without the
            exclusion) to fold the new transaction into the profile.
        reference_ts: velocity/recency windows are measured relative to the
            reference event time (the transaction being scored) instead of
            wall-clock `datetime.now()`, so scores are deterministic and
            backfill/seed data computes correctly.
        """
        query = self.db.query(Transaction).filter(
            Transaction.customer_id == customer_id
        )
        if exclude_transaction_id:
            query = query.filter(Transaction.transaction_id != exclude_transaction_id)
        txns = query.order_by(Transaction.timestamp.desc()).all()

        if not txns:
            return self.get_or_create_profile(customer_id)

        amounts = [t.amount for t in txns]
        hours = [t.timestamp.hour for t in txns if t.timestamp]
        categories = {}
        devices = set()
        locations = set()

        for t in txns:
            if t.merchant_category:
                categories[t.merchant_category] = categories.get(t.merchant_category, 0) + 1
            if t.device_id:
                devices.add(t.device_id)
            if t.location_city:
                locations.add(t.location_city)

        total = len(txns)
        cat_probs = {k: v / total for k, v in categories.items()}

        ref = reference_ts or datetime.now(timezone.utc)
        if getattr(ref, "tzinfo", None) is None:
            ref = ref.replace(tzinfo=timezone.utc)
        else:
            ref = ref.astimezone(timezone.utc)

        recent_5 = [t.amount for t in txns if t.timestamp and (ref - t.timestamp.replace(tzinfo=timezone.utc)).total_seconds() < 300]
        recent_15 = [t.amount for t in txns if t.timestamp and (ref - t.timestamp.replace(tzinfo=timezone.utc)).total_seconds() < 900]
        recent_60 = [t.amount for t in txns if t.timestamp and (ref - t.timestamp.replace(tzinfo=timezone.utc)).total_seconds() < 3600]

        hour_counts = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1

        days_span = max(1, (txns[0].timestamp - txns[-1].timestamp).days if len(txns) > 1 else 1)

        profile = self.get_or_create_profile(customer_id)
        profile.avg_transaction_amount = float(np.mean(amounts))
        profile.std_transaction_amount = float(np.std(amounts)) if len(amounts) > 1 else 0
        profile.median_transaction_amount = float(np.median(amounts))
        profile.max_transaction_amount = float(max(amounts))
        profile.total_transactions = total
        profile.avg_transactions_per_day = total / days_span
        profile.common_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[:5]
        profile.common_categories = cat_probs
        profile.common_devices = list(devices)
        profile.common_locations = list(locations)
        profile.avg_amount_last_5 = float(np.mean(recent_5)) if recent_5 else profile.avg_transaction_amount
        profile.avg_amount_last_15 = float(np.mean(recent_15)) if recent_15 else profile.avg_transaction_amount
        profile.avg_amount_last_60 = float(np.mean(recent_60)) if recent_60 else profile.avg_transaction_amount
        profile.tx_count_last_5 = len(recent_5)
        profile.tx_count_last_15 = len(recent_15)
        profile.tx_count_last_60 = len(recent_60)
        profile.last_updated = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def calculate_deviation(self, transaction: Transaction, profile: BehavioralProfile = None) -> float:
        if profile is None:
            profile = self.get_or_create_profile(transaction.customer_id)

        if profile.total_transactions < 3:
            return 50.0

        deviations = []

        if profile.avg_transaction_amount > 0:
            amt_ratio = transaction.amount / (profile.avg_transaction_amount + 1)
            amt_dev = min(100, max(0, (amt_ratio - 1) * 30))
            deviations.append(amt_dev * 0.35)

        if profile.std_transaction_amount > 0:
            z_score = abs(transaction.amount - profile.avg_transaction_amount) / (profile.std_transaction_amount + 1)
            z_dev = min(100, z_score * 25)
            deviations.append(z_dev * 0.25)
        else:
            deviations.append(0)

        if transaction.timestamp:
            hour = transaction.timestamp.hour
            if profile.common_hours and hour not in profile.common_hours:
                deviations.append(30)
            else:
                deviations.append(0)

        if transaction.device_id and profile.common_devices:
            if transaction.device_id not in profile.common_devices:
                deviations.append(40)
            else:
                deviations.append(0)

        if transaction.location_city and profile.common_locations:
            if transaction.location_city not in profile.common_locations:
                deviations.append(35)
            else:
                deviations.append(0)

        if transaction.merchant_category and profile.common_categories:
            cat_prob = profile.common_categories.get(transaction.merchant_category, 0)
            cat_dev = max(0, (1 - cat_prob) * 60)
            deviations.append(cat_dev * 0.15)

        score = sum(deviations) if deviations else 0
        return min(100, max(0, round(score, 2)))
