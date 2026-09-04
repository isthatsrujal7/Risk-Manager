"""Single source of truth for risk tiers and human-in-the-loop bands.

Used by the scoring service, the seed script, the README, and .env.example so
thresholds can't drift between layers.
"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# HITL decision bands (these are the contractual thresholds):
#   [0, BAND_AUTOPILOT_MAX)            -> AI_AUTOPILOT   (auto pass)
#   [BAND_AUTOPILOT_MAX, BAND_BLOCK_MIN) -> HUMAN_REVIEW  (alert risk team)
#   [BAND_BLOCK_MIN, 100]              -> AI_MANAGED_BLOCK (AI holds the txn)
BAND_AUTOPILOT_MAX = float(os.getenv("RISK_BAND_AUTOPILOT_MAX", "25"))
BAND_BLOCK_MIN = float(os.getenv("RISK_BAND_BLOCK_MIN", "90"))

# Display-only risk tiers. LOW/MEDIUM/HIGH fit in the autopilot+review bands,
# CRITICAL enters the block band.
TIER_LOW_MAX = BAND_AUTOPILOT_MAX
TIER_MEDIUM_MAX = 60.0
TIER_HIGH_MAX = BAND_BLOCK_MIN
TIER_CRITICAL_MAX = 100.0


def risk_tier(score: float) -> str:
    if score < TIER_LOW_MAX:
        return "LOW"
    if score < TIER_MEDIUM_MAX:
        return "MEDIUM"
    if score < TIER_HIGH_MAX:
        return "HIGH"
    return "CRITICAL"


def hitl_band(score: float) -> str:
    if score < BAND_AUTOPILOT_MAX:
        return "AI_AUTOPILOT"
    if score >= BAND_BLOCK_MIN:
        return "AI_MANAGED_BLOCK"
    return "HUMAN_REVIEW"