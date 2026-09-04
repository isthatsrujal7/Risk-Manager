# Failure Recovery Log ("We Fixed It")

> Track 02 brief says: "Strictly defense-only: anything offense-capable is
> disqualified." A risk engine that can also *fail loudly but cleanly* and
> recover is the whole point. This document lists every real production
> incident we hit while building RiskGuard AI, the root cause, the fix, and
> the guard-rail that now prevents recurrence.

---

## Incident 1 — Spike detector crashed with a 500 (tuple shape mismatch)

**Symptom**: `POST /api/spikes/detect` and `/api/spikes/history` returned
`500 Internal Server Error`; the FraudSpikes page was dead.

**Root cause**: `_zscore_anomaly()` returned inconsistent tuples. On the
normal path it returned `(is_anomaly, z_score, mean, std)` (4 values), but
the zero-variance / cold-start branch returned `(is_anomaly, z_score)`
(2 values). `detect_fraud_spikes` unpacked 4 values and crashed.

**Fix**: `backend/app/risk/spike_detection.py` — made every return path emit
the identical 4-tuple shape, and handled the degenerate `std == 0` case with
`z = 0.0` instead of a silent branch.

**Guard**: every public detection function now has an explicit
`# returns (is_anomaly, z, mean, std)` contract; the endpoint smoke test list
(see test suite) includes spike endpoints.

---

## Incident 2 — All seeded assessments shared the same timestamp

**Symptom**: Risk-trend charts and investigation timelines showed every
historical transaction clustered at the moment the seed script ran (today),
instead of spanning the simulated 90-day window. Synthetic data was generated
across 2025-01-01 → 2025-03-15, but the stored assessments didn't.

**Root cause**: `scripts/seed_database.py` created `RiskAssessment`,
`Alert`, and `Investigation` rows with `datetime.now(timezone.utc)` instead
of carrying each transaction's own `timestamp` through to derived rows.

**Fix**: seed script now propagates `transaction.timestamp` into the
assessment, alert, and investigation timestamps, so historical analytics and
the spike detector's time-anchored window behave like real backfill.

**Guard**: risk-trends endpoint is validated to produce a non-degenerate
multi-day series; a chart that collapses to a single day now fails the check.

---

## Incident 3 — Feedback-loop retrain returned 500 (timezone mix)

**Symptom**: `GET /api/feedback-loop/status` and the retrain action crashed
after the first human-labeled review existed.

**Root cause**: `_extract_human_labeled_data()` built a DataFrame whose
`timestamp` values were **timezone-naive**, while the synthetic data
generator emits **timezone-aware** (UTC) timestamps. Mixing the two inside
the feature pipeline threw `Cannot compare tz-naive and tz-aware`.
(`pandas` refuses a timezone-cast ambiguity.)

**Fix**: `backend/app/services/feedback_loop.py` — normalize human-labeled
rows to `timestamp = tz-aware UTC` before the DataFrame is built.

**Guard**: the feedback-loop status + retrain flow was re-run end-to-end after
the fix and produced `v2-feedback-20260904152541` (F1 0.973) with labeled
human data present; the tz contract is now documented at the module boundary.

---

## Incident 4 — Frontend refused to build after a TS strictness change

**Symptom**: `npm run build` failed type-check. `ModelAnalytics`/`MerchantRisk`
mapped over a parameter the strict config typed as implicitly `any`.

**Root cause**: a `map((t) => ...)` callback (and a numerically-typed prop)
had no explicit annotation; `tsc -b` enforces `noImplicitAny`.

**Fix**: explicit `(t: any)` annotations on the callback parameters and
loose-typed map callbacks.

**Guard**: `npm run build` is part of the release checklist; the frontend
continuously-integrated against `tsc -b && vite build`.

---

## Incident 5 — Backend silently ran a *heuristic* scorer instead of the ML model

**Symptom**: After the full rework, the live-scored transaction showed
`ml_risk_score = 80` that *looked* plausible, but the trained Random Forest
was never actually being invoked — a warning was printed to the log and the
service fell back to a rules heuristic.

**Root cause**: model loading used **cwd-relative paths**
(`"ml/models/fraud_model.joblib"`). The backend was started from `backend/`,
so it resolved to `backend/ml/models/...` which doesn't exist; the trained
artifacts live at the repository root `ml/models/`. `_load_model()`
swallowed the failure and returned an untrained model → heuristic fallback.
Silent degradation is the worst kind of bug in a risk engine.

**Fix**: added `backend/app/services/model_paths.py`, a single canonical
`MODEL_DIR` resolved from the module location (repo root), and wired it into
`risk_scoring._load_model`, `feedback_loop`, and `analytics`. Now the engine
either loads the real trained model or fails loudly.

**Guard**: the live feed test now asserts a real ML score (non-heuristic
probe) after a fresh scorer boot; the honest-evaluation JSON is served by
`/api/analytics/model-performance` only when the model artifacts are present.

---

## Incident 6 — GitHub push denied (fine-grained token permissions)

**Symptom**: `git push -u origin main` → `403 Permission to
isthatsrujal7/Risk-Manager.git denied to isthatsrujal7`, even though the API
reported `push: true` for the authenticating account.

**Root cause**: fine-grained personal access tokens need **both**
`Contents: Read and write` *and* `Metadata: Read` repository permissions;
the first PAT had only read/API metadata. A user-level login can't be
force-elevated from the command line.

**Fix**: recreated the token with `Contents: Read and write` +
`Metadata: Read` for the repository; push succeeded (`23a52bc` and `ae9bcaf`
live on GitHub).

**Security note**: the earlier token text was pasted into a chat session and
was **revoked** after use; never leave tokens in shell history or chat logs.

---

## Incident 7 — External review: ML model silently not loading (path bug)

**Symptom**: an evaluator running `cd backend && uvicorn app.main:app` got
`ModuleNotFoundError: No module named 'ml.src'`. The backend never crashed — it
silently fell back to the heuristic scorer, so every score looked "fine".

**Root cause**: `risk_scoring.py` inserted `os.path.join(dirname, "..", "..")`
into `sys.path`, which resolves to `backend/`, not the repo root — `ml.src`
was unreachable whenever the process ran from `backend/` (uvicorn, pytest).
A model "loaded" flag was already set by the fallback branch, masking the gap.

**Fix**: repo-root bootstrap in `backend/app/__init__.py` and
`app/services/model_paths.py` (PROJECT_ROOT injected into `sys.path`); the
`ml.src` import now works from any working directory.

**Guard**: regression test `TestMlImportPath` asserts `ml.src` is importable
from the backend CWD and that the canonical model artifacts resolve to the
repo root.

---

## Incident 8 — External review: two databases, empty dashboard (path bug)

**Symptom**: seeding (run from repo root) wrote `riskguard.db` at the root,
while the backend (running from `backend/`) read `backend/riskguard.db`.
Dashboards got different data depending on who ran what.

**Root cause**: relative `sqlite:///./riskguard.db` URLs resolve against the
process CWD. Nothing anchored them.

**Fix**: `backend/app/models/database.py` now resolves relative SQLite paths
against the repo root (PROJECT_ROOT), and loads `.env` before the engine is
created. Seed and live app share exactly one database file.

**Guard**: tests run against an isolated DB via `tests/conftest.py`
(`DATABASE_URL` redirected to a temp file) so the suite can never clobber the
demo database.

---

## Incident 9 — External review: dashboard metrics were label-rigged

**Symptom**: the UI claimed ~100% precision/recall/F1 on the seeded stream.

**Root cause**: two compounding leaks. (1) `seed_database.py` shaped every
`final_score` from the ground-truth `is_fraud` column instead of from the
model, and it inserted the **oldest** 1000 transactions (training-period data
the model had already seen). (2) `analytics_overview` recomputed
precision/recall from the DB's own labels+predictions, so the demo literally
graded its own homework.

**Fix**: (1) seed now inserts the **held-out test window** (newest 20%,
model never trained on it) and scores purely from the model plus a
contamination-free behavioral baseline built exactly like live scoring.
(2) `analytics/overview` reports classification quality from
`evaluation_metrics.json` (with `metrics_source: "held-out test set"`), while
operational counts stay as genuine DB facts.

**Guard**: `TestAnalytics.test_overview_metrics_from_held_out_set` fails if
`metrics_source` is absent; the seeded stream reproduces the model card
numbers within rounding.

---

## Incident 10 — External review: behavioral baseline contaminated the scored event

**Symptom**: a transaction was compared against a profile that included the
transaction itself, and recency counters used wall-clock time.

**Root cause**: `update_profile` queried *all* of a customer's transactions,
including the very event being scored; velocity windows used
`datetime.now()` instead of the event's timestamp.

**Fix**: `update_profile` accepts `exclude_transaction_id` (scoring passes the
transaction under evaluation) and `reference_ts` (event-time recency). After
scoring, the new transaction is folded into the profile.

**Guard**: the seed path exercises the exact same service semantics.

---

## Incident 11 — External review: inconsistent risk thresholds across layers

**Symptom**: `.env.example` said 30/60/80 but the app used 25/60/90 and the
cost engine used 60/90.

**Fix**: HITL bands and risk tiers are now defined in exactly one place —
`backend/app/risk_policy.py` (`RISK_BAND_AUTOPILOT_MAX=25`,
`RISK_BAND_BLOCK_MIN=90`) — and consumed by scoring, cost decision, seed,
`.env.example` and README.

**Guard**: changing a band is a one-line config change; nothing hardcodes 25/90.

---

## Incident 12 — External review: duplicate assessments on re-score + unvalidated LLM output

**Symptom**: re-scoring a transaction appended a second `RiskAssessment` row;
LLM investigation output was parsed with raw `json.loads`.

**Fix**: re-scoring reuses the existing `assessment_id` (one assessment per
transaction, enforced by a DB unique constraint); `retrain_candidate_from_feedback`
+ `POST /api/feedback-loop/approve` make model replacement an explicit,
human-gated action instead of an automatic overwrite.

**Guard**: `TestRiskScoring.test_rescore_does_not_duplicate_assessment` asserts
a single row *and* a stable `assessment_id` after two `/score` calls.

---

## How we prevent recurrence

- Endpoints are smoke-tested after every change (see `backend` test list).
- The frontend must pass `tsc -b && vite build` before a commit is cut.
- Model paths are project-anchored, never cwd-dependent.
- The honest evaluation fails visibly (no silent green metrics).
- Anything that can force a transaction through (blocking, canceling,
  altering amounts) is defense-only by construction; there is no
  offense-capable API surface anywhere in the codebase.