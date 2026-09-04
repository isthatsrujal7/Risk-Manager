# 5-Minute Demo Script

## Setup
- Backend running on localhost:8000
- Frontend running on localhost:5173
- Database seeded with 1,000 transactions

## Story

### 1. Problem (30s)
"Fraud detection systems can flag transactions, but risk teams need context, explanation, and actionable workflows. RiskGuard AI provides all of this in one platform."

### 2. Dashboard Overview (30s)
Show the dashboard with:
- 1,000 transactions analyzed
- 51 high-risk cases
- Precision/recall metrics
- Risk distribution chart
- Business cost analysis

### 3. Normal Transaction (30s)
- Navigate to Transactions
- Click a LOW risk transaction
- Show: low risk score, ALLOW recommendation
- "Normal transactions flow through with minimal friction"

### 4. Suspicious Transaction (60s)
- Click a HIGH/CRITICAL risk transaction
- Show: ML score, behavioral deviation score, top signals
- Highlight the personalized behavioral analysis

### 5. AI Investigation (60s)
- Click "Run AI Investigation"
- Show the investigation report:
  - Risk summary
  - Evidence (all sourced from backend tools, no hallucination)
  - Contributing factors
  - Behavioral anomalies
  - Related activity
  - Uncertainty disclosure
  - Recommendation with reasoning

### 6. Human Review (60s)
- Navigate to Review Queue
- Select a pending review
- Show: transaction details, AI recommendation, investigation report
- Make a decision (approve/reject)
- Show decision recorded

### 7. Audit Trail (30s)
- Navigate to Audit Trail
- Show the timeline of events for that transaction
- "Every decision is tracked with full audit trail"

### 8. Model Analytics (30s)
- Navigate to Model Analytics
- Show precision, recall, F1
- Show confusion matrix
- Show feedback summary
- "All metrics from held-out test set"

### 9. Three Differentiators (30s)
- **AI Investigation Agent**: Grounded investigation using backend tools
- **Behavioral Risk Fingerprint**: Personalized risk per customer
- **Feedback Learning Loop**: Human decisions feed back into monitoring

## Key Points to Emphasize

- ML does the scoring, not the LLM
- The investigation agent cannot invent evidence
- Human review is required for high-impact decisions
- All metrics are from a held-out test set
- Business costs are simulated with documented assumptions
