import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta, timezone


def generate_synthetic_data(n_customers=200, n_transactions=5000, fraud_rate=0.05, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    customers = []
    for i in range(n_customers):
        cust_id = f"CUST-{i:05d}"
        avg_amt = np.random.lognormal(mean=6, sigma=1.2)
        customers.append({
            "customer_id": cust_id,
            "avg_amount": avg_amt,
            "std_amount": avg_amt * np.random.uniform(0.2, 0.8),
            "preferred_categories": random.sample(
                ["electronics", "groceries", "travel", "dining", "entertainment",
                 "fashion", "utilities", "healthcare", "fuel", "education"],
                k=random.randint(2, 5)
            ),
            "preferred_devices": [f"DEV-{random.randint(1000,9999)}" for _ in range(random.randint(1, 3))],
            "preferred_cities": random.sample(
                ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata",
                 "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow"],
                k=random.randint(1, 3)
            ),
            "typical_hour": random.randint(8, 22),
            "account_age_days": random.randint(30, 1800),
        })

    rows = []
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n_transactions):
        cust = random.choice(customers)
        is_fraud = random.random() < fraud_rate

        if is_fraud:
            amt = cust["avg_amount"] * np.random.uniform(3, 15)
            hour = random.choice([1, 2, 3, 4, 5, 23])
            cat = random.choice(["electronics", "travel", "utilities"])
            device = f"DEV-{random.randint(10000, 99999)}"
            city = random.choice(["Unknown", "Foreign", "Nairobi", "Moscow", "Lagos"])
        else:
            amt = max(10, np.random.normal(cust["avg_amount"], cust["std_amount"]))
            hour = max(0, min(23, int(np.random.normal(cust["typical_hour"], 3))))
            cat = random.choice(cust["preferred_categories"])
            device = random.choice(cust["preferred_devices"])
            city = random.choice(cust["preferred_cities"])

        ts = start_date + timedelta(
            days=random.randint(0, 364),
            hours=hour,
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        payment_methods = ["upi", "credit_card", "debit_card", "netbanking", "wallet"]
        if is_fraud:
            pay_method = random.choice(["credit_card", "debit_card", "wallet"])
        else:
            pay_method = random.choice(payment_methods)

        merchants = {
            "electronics": ["Flipkart", "Amazon", "Croma", "Reliance Digital"],
            "groceries": ["BigBasket", "Zepto", "Blinkit", "DMart"],
            "travel": ["MakeMyTrip", "OYO", "IRCTC", "Goibibo"],
            "dining": ["Zomato", "Swiggy", "Dominos", "KFC"],
            "entertainment": ["Netflix", "Hotstar", "BookMyShow", "Spotify"],
            "fashion": ["Myntra", "Ajio", "Nykaa", "H&M"],
            "utilities": ["Paytm", "PhonePe", "BSES", "Jio"],
            "healthcare": ["PharmEasy", "1mg", "Medlife", "Practo"],
            "fuel": ["Indian Oil", "HP", "BP", "Reliance Petroleum"],
            "education": ["BYJU's", "Unacademy", "Coursera", "Udemy"],
        }

        rows.append({
            "transaction_id": f"TXN-{i:06d}",
            "customer_id": cust["customer_id"],
            "amount": round(amt, 2),
            "currency": "INR",
            "payment_method": pay_method,
            "merchant_category": cat,
            "merchant_name": random.choice(merchants.get(cat, ["Unknown"])),
            "device_id": device,
            "ip_address": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}",
            "location_city": city,
            "location_country": "IN" if city not in ["Unknown", "Foreign", "Nairobi", "Moscow", "Lagos"] else random.choice(["KE", "RU", "NG"]),
            "timestamp": ts.isoformat(),
            "is_fraud": is_fraud,
            "account_age_days": cust["account_age_days"],
            "customer_avg_amount": cust["avg_amount"],
            "customer_std_amount": cust["std_amount"],
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    n_test = int(n_transactions * 0.2)
    n_val = int(n_transactions * 0.1)
    train_df = df.iloc[:-(n_test + n_val)]
    val_df = df.iloc[-(n_test + n_val):-n_test]
    test_df = df.iloc[-n_test:]

    return {
        "customers": pd.DataFrame(customers),
        "train": train_df,
        "val": val_df,
        "test": test_df,
        "full": df,
    }
