"""Cost-aware risk decisioning engine.

Picks the best action for a transaction by expected rupee loss rather than a
fixed score threshold. For each transaction we compare the two realistic
outcomes:

  Allow:
    expected loss = P(fraud | signal) * amount * fraud_loss_rate
                    - (false acceptance: we pay the fraud amount in full)

  Flag (review/block):
    expected loss = friction of reviewing/blocking a good order
                    + (uncaught fraud that slips past the gate)

The *best* action is whichever has the lower expected cost. This derives a
per-transaction break-even probability:

  break_even = friction / (amount * loss_rate)

A transaction is worth intervening on when its risk (probability of fraud)
exceeds break_even. This is a purely defensive, advisory layer: it never
blocks or charges anything by itself.
"""
from dataclasses import dataclass, asdict

from app import risk_policy


@dataclass
class CostDecision:
    decision: str                 # ALLOW | VERIFY | REVIEW | BLOCK
    decision_reason: str
    expected_loss_allow: float    # expected ₹ loss if we let it through
    expected_loss_flag: float     # expected ₹ loss if we flag/review
    expected_saving: float        # expected_loss_allow - expected_loss_flag
    break_even_prob: float        # risk threshold where flagging pays for itself
    handling_friction: float      # assumed ₹ cost to review a good order
    fraud_loss_rate: float        # portion of amount lost on a fraud (1.0)
    prevention_rate: float        # how much of caught fraud we prevent
    risk_score: float             # normalized 0-100 risk


# Tunable, documented, conservative assumptions (mirrors pre-dispatch scorer's
# "named cost assumptions" approach). Meant to be swept in a sensitivity test,
# not presented as ground truth.
DEFAULT_FRICTION_PER_REVIEW = 25.0    # ₹ cost of reviewing one non-fraud order
DEFAULT_FRAUD_LOSS_RATE = 1.0         # losing 100% of the fraud amount
DEFAULT_PREVENTION_RATE = 0.5         # catching a fraud prevents half of its loss


def compute_cost_decision(
    amount: float,
    risk_score: float,
    friction_per_review: float = DEFAULT_FRICTION_PER_REVIEW,
    fraud_loss_rate: float = DEFAULT_FRAUD_LOSS_RATE,
    prevention_rate: float = DEFAULT_PREVENTION_RATE,
) -> CostDecision:
    if amount <= 0:
        amount = 100.0
    p_fraud = max(0.0, min(1.0, risk_score / 100.0))

    fraud_amount = amount * fraud_loss_rate

    # If we allow, we are exposed to the full fraud loss with probability p.
    expected_loss_allow = p_fraud * fraud_amount

    # If we flag, we pay friction on the order regardless, but prevent a
    # fraction of the fraud we catch. (Nowhere near perfect — honest.)
    expected_loss_flag = friction_per_review + (
        p_fraud * fraud_amount * (1.0 - prevention_rate)
    )

    expected_saving = expected_loss_allow - expected_loss_flag
    break_even = friction_per_review / (fraud_amount * prevention_rate) if fraud_amount > 0 else 1.0

    if expected_saving > 0:
        # Intervening is cheaper than letting it through.
        if risk_score >= risk_policy.BAND_BLOCK_MIN:
            # Preserve the HITL three-tier rule: block-band scores are auto-blocked.
            decision = "BLOCK"
            reason = f"Expected loss if allowed exceeds handling cost; high confidence fraud (score >= {risk_policy.BAND_BLOCK_MIN:.0f})."
        elif risk_score >= risk_policy.TIER_MEDIUM_MAX:
            decision = "REVIEW"
            reason = "Expected loss if allowed exceeds handling cost; send to human review."
        else:
            decision = "VERIFY"
            reason = "Expected loss if allowed exceeds handling cost; verify before proceeding."
    else:
        decision = "ALLOW"
        reason = "Handling cost exceeds expected fraud loss; allow through with monitoring."

    return CostDecision(
        decision=decision,
        decision_reason=reason,
        expected_loss_allow=round(expected_loss_allow, 2),
        expected_loss_flag=round(expected_loss_flag, 2),
        expected_saving=round(expected_saving, 2),
        break_even_prob=round(break_even, 4),
        handling_friction=friction_per_review,
        fraud_loss_rate=fraud_loss_rate,
        prevention_rate=prevention_rate,
        risk_score=round(risk_score, 2),
    )


def cost_decision_dict(
    amount: float,
    risk_score: float,
    friction_per_review: float = DEFAULT_FRICTION_PER_REVIEW,
    fraud_loss_rate: float = DEFAULT_FRAUD_LOSS_RATE,
    prevention_rate: float = DEFAULT_PREVENTION_RATE,
) -> dict:
    return asdict(compute_cost_decision(
        amount, risk_score, friction_per_review, fraud_loss_rate, prevention_rate
    ))