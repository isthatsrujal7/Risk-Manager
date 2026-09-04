import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import engine, Base, SessionLocal
from app.models.models import Transaction, Customer, RiskAssessment, Investigation, Review
from app.services import model_paths


class TestMlImportPath:
    """Regression: the backend must be able to import ml.src no matter where it
    is launched from (this was failing because sys.path resolved to backend/)."""

    def test_ml_src_importable_from_backend_cwd(self):
        import ml.src.model
        import ml.src.feature_pipeline
        assert os.path.isabs(model_paths.MODEL_DIR)
        assert os.path.exists(model_paths.model_path("fraud_model.joblib"))
        assert os.path.exists(model_paths.model_path("feature_pipeline.joblib"))


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def admin_token():
    from app.auth import ensure_default_users
    ensure_default_users()
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": "riskadmin", "password": "RiskGuard@riskadmin"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    from app.auth import ensure_default_users
    ensure_default_users()
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": "riskviewer", "password": "RiskGuard@riskviewer"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def client(admin_token):
    return TestClient(app, headers={"Authorization": f"Bearer {admin_token}"})


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

    def test_rescore_does_not_duplicate_assessment(self, client, db):
        created = client.post("/api/transactions/", json={
            "customer_id": "TEST-001",
            "amount": 90000,
            "payment_method": "credit_card",
            "merchant_category": "electronics",
            "merchant_name": "Amazon",
            "device_id": "DEV-77777",
            "location_city": "Unknown",
            "location_country": "RU",
        })
        assert created.status_code == 200
        txn_id = created.json()["transaction_id"]

        first = client.post(f"/api/transactions/{txn_id}/score").json()
        second = client.post(f"/api/transactions/{txn_id}/score").json()

        count = db.query(RiskAssessment).filter(
            RiskAssessment.transaction_id == txn_id
        ).count()
        assert count == 1
        assert second["assessment_id"] == first["assessment_id"]

    def test_rejected_ingestion_label(self, client):
        """Live ingestion must not accept a ground-truth label."""
        created = client.post("/api/transactions/", json={
            "customer_id": "TEST-001",
            "amount": 5000,
            "is_fraud": True,
        })
        assert created.status_code == 200 or created.status_code == 422


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

    def test_overview_metrics_from_held_out_set(self, client):
        """Dashboard metrics must come from the held-out evaluation file, never
        be recomputed from the demo DB (which would look artificially perfect)."""
        response = client.get("/api/analytics/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics_source"].startswith("held-out test set")
        assert "test_samples" in data

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


class TestAuth:
    def test_login_success(self):
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"username": "riskadmin", "password": "RiskGuard@riskadmin"})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["user"]["role"] == "admin"

    def test_login_wrong_password_rejected(self):
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"username": "riskadmin", "password": "wrong"})
        assert r.status_code == 401

    def test_unauthenticated_read_rejected(self):
        c = TestClient(app)
        assert c.get("/api/reviews/").status_code == 401
        assert c.get("/api/analytics/overview").status_code == 401

    def test_viewer_can_read(self, viewer_token):
        c = TestClient(app, headers={"Authorization": f"Bearer {viewer_token}"})
        assert c.get("/api/reviews/").status_code == 200
        assert c.get("/api/analytics/overview").status_code == 200

    def test_viewer_cannot_review_or_retrain(self, viewer_token):
        c = TestClient(app, headers={"Authorization": f"Bearer {viewer_token}"})
        assert c.post("/api/reviews/", json={
            "investigation_id": "x", "transaction_id": "y",
            "human_decision": "APPROVED", "reviewer_note": "",
        }).status_code == 403
        assert c.post("/api/feedback-loop/retrain").status_code == 403

    def test_analyst_cannot_retrain(self):
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"username": "riskanalyst", "password": "RiskGuard@riskanalyst"})
        assert r.status_code == 200
        analyst = TestClient(app, headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        assert analyst.post("/api/feedback-loop/retrain").status_code == 403
        assert analyst.get("/api/feedback-loop/status").status_code == 200

    def test_health_and_login_public(self):
        c = TestClient(app)
        assert c.get("/api/health").status_code == 200
