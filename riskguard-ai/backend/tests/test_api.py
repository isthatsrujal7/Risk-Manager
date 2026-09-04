import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import engine, Base, SessionLocal
from app.models.models import Transaction, Customer, RiskAssessment, Investigation, Review


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def seed_minimal_data(db):
    cust = Customer(customer_id="TEST-001", name="Test Customer")
    db.add(cust)

    txn = Transaction(
        transaction_id="TEST-TXN-001",
        customer_id="TEST-001",
        amount=5000,
        payment_method="upi",
        merchant_category="groceries",
        merchant_name="BigBasket",
        device_id="DEV-1001",
        location_city="Mumbai",
        location_country="IN",
    )
    db.add(txn)

    txn2 = Transaction(
        transaction_id="TEST-TXN-002",
        customer_id="TEST-001",
        amount=100000,
        payment_method="credit_card",
        merchant_category="electronics",
        merchant_name="Amazon",
        device_id="DEV-9999",
        location_city="Unknown",
        location_country="RU",
    )
    db.add(txn2)

    db.commit()
    return txn, txn2


class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestTransactions:
    def test_list_transactions_empty(self, client):
        response = client.get("/api/transactions/")
        assert response.status_code == 200

    def test_create_transaction(self, client):
        response = client.post("/api/transactions/", json={
            "customer_id": "TEST-001",
            "amount": 15000,
            "payment_method": "upi",
            "merchant_category": "dining",
            "merchant_name": "Zomato",
        })
        assert response.status_code == 200
        data = response.json()
        assert "transaction_id" in data
        assert "risk_assessment" in data
        assert data["risk_assessment"]["final_risk_score"] >= 0

    def test_get_nonexistent_transaction(self, client):
        response = client.get("/api/transactions/NONEXISTENT")
        assert response.status_code == 404


class TestRiskScoring:
    def test_risk_distribution(self, client):
        response = client.get("/api/risk/distribution")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "LOW" in data

    def test_risk_scores(self, client):
        response = client.get("/api/risk/scores")
        assert response.status_code == 200


class TestReviews:
    def test_pending_count(self, client):
        response = client.get("/api/reviews/pending-count")
        assert response.status_code == 200
        assert "pending_count" in response.json()

    def test_list_reviews(self, client):
        response = client.get("/api/reviews/")
        assert response.status_code == 200


class TestAnalytics:
    def test_overview(self, client):
        response = client.get("/api/analytics/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_transactions" in data
        assert "precision" in data
        assert "recall" in data

    def test_model_performance(self, client):
        response = client.get("/api/analytics/model-performance")
        assert response.status_code == 200

    def test_audit_trail(self, client):
        response = client.get("/api/analytics/audit-trail")
        assert response.status_code == 200


class TestFeedback:
    def test_feedback_summary(self, client):
        response = client.get("/api/feedback/summary")
        assert response.status_code == 200

    def test_error_patterns(self, client):
        response = client.get("/api/feedback/errors")
        assert response.status_code == 200

    def test_export_feedback(self, client):
        response = client.get("/api/feedback/export")
        assert response.status_code == 200


class TestInvestigations:
    def test_list_investigations(self, client):
        response = client.get("/api/investigations/")
        assert response.status_code == 200
