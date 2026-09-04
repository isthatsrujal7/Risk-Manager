from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from app.api.transactions import router as transactions_router
from app.api.risk import router as risk_router
from app.api.investigations import router as investigations_router
from app.api.reviews import router as reviews_router
from app.api.feedback import router as feedback_router
from app.api.analytics import router as analytics_router
from app.api.audit import router as audit_router
from app.api.fraud_patterns import router as fraud_patterns_router
from app.api.spikes import router as spikes_router
from app.api.merchants import router as merchants_router
from app.api.live import router as live_router
from app.api.alerts import router as alerts_router
from app.api.feedback_loop import router as feedback_loop_router
from app.api.auth import router as auth_router
from app.models.database import engine, Base
from app.auth import ensure_default_users

load_dotenv()

Base.metadata.create_all(bind=engine)
ensure_default_users()

app = FastAPI(
    title="RiskGuard AI",
    description="AI Risk Investigation & Adaptive Fraud Management System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions_router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(risk_router, prefix="/api/risk", tags=["Risk Scoring"])
app.include_router(investigations_router, prefix="/api/investigations", tags=["Investigations"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(feedback_router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(audit_router, prefix="/api/audit", tags=["Audit"])
app.include_router(fraud_patterns_router, prefix="/api/fraud-patterns", tags=["Fraud Patterns"])
app.include_router(spikes_router, prefix="/api/spikes", tags=["Fraud Spike Detection"])
app.include_router(merchants_router, prefix="/api/merchants", tags=["Merchant Risk"])
app.include_router(live_router, prefix="/api/live", tags=["Real-time Monitoring"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["Alert System"])
app.include_router(feedback_loop_router, prefix="/api/feedback-loop", tags=["Model Feedback Loop"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "RiskGuard AI"}
