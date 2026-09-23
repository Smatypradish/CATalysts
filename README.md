# CAT Operator Companion

An intelligent operator assistant for CAT machinery, built for the hackathon problem
statement. It combines task-time prediction, a deterministic real-time safety rule
engine, unusual behavior detection, behaviour-linked training recommendations and a
grounded AI assistant — in one operator-facing web app.

## Problem

Heavy-equipment operators juggle task scheduling, safety compliance and fuel/idle
efficiency. Supervisors lack real-time visibility into unsafe behavior, and training
assignments are generic instead of tied to observed behavior. The companion gives the
operator a single dashboard that predicts task durations, watches safety sensors in
real time, detects unusual operating behavior, and recommends targeted training.

## Solution overview

| Capability | How it works |
|---|---|
| Operator dashboard | Live status of machine, safety posture, today's tasks, AI-generated insights |
| Task time prediction | scikit-learn `GradientBoostingRegressor` + `OneHotEncoder(task_type, weather, skill)` + machine age; counterfactual factor explanations |
| Real-time safety monitoring | **Deterministic rule engine only** (seatbelt, proximity) with weather-adjusted thresholds; CRITICAL alerts fire instantly and are logged |
| Unusual behavior detection | Policy rules + per-operator z-scores vs baseline + `IsolationForest` outliers; every finding explains *what / why / action* |
| Training recommendations | Findings are mapped to training modules (e.g. excessive idling → TM-IDLE) — derived from data, not hardcoded |
| AI assistant | Intent-classified, grounded answers over the app's own data (safety status, predictions, behavior findings). Not an open chatbot — answers always cite the data they used |
| Incident log & history | Incidents can be acknowledged/resolved; completed tasks show predicted vs actual with variance |

### Safety-first architecture decision

Safety alerts (seatbelt, proximity) are produced **only** by deterministic rules in
`backend/app/services/safety_rules.py`. Proximity warning/critical thresholds are
enlarged under adverse working conditions (Rainy 1.4x, Fog 1.5x, Night 1.3x, ...).
ML is used **only** for behavior anomaly detection and task time prediction — never
for safety-critical decisions. The AI assistant cannot override or silence rules.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + SQLite, scikit-learn, pandas/numpy, Uvicorn
- **Frontend:** React 18, Vite, Tailwind CSS, React Router, lucide-react, axios
- **Data:** the two supplied CSV datasets (loaded verbatim) + clearly-labelled
  synthetic/simulated rows

## Datasets used

- `data/machine_telemetry.csv` (Dataset 1, 4 rows) — engine hours, fuel used, load
  cycles, idling time, seatbelt status, safety alerts. Loaded verbatim with
  `source="dataset"`; drives behavior baselines and findings (the supplied rows
  contain 50–65 min idling and an unfastened-seatbelt record — the analyzer flags both).
- `data/task_records.csv` (Dataset 2, 5 rows) — task type, weather, operator skill,
  machine age, estimated vs actual time. These 5 real rows train the prediction model.

### Small-dataset honesty

5 rows cannot train a reliable regressor, so the model is augmented with 50 labelled
synthetic rows (`source="synthetic"`, formula documented in `backend/app/seed.py`).
Every prediction response and the UI footer disclose: rows used (real vs synthetic),
algorithm, and the **leave-one-out MAE computed on the 5 real rows only** (~10 min),
with an explicit disclaimer that this is not production accuracy. All simulated
telemetry is tagged `source="simulated"` and shown with badges in the UI.

## Project structure

```
CAT-Operator-Companion/
  data/                     # supplied CSV datasets
  backend/
    run.py                  # start server (seeds DB + trains model on boot)
    seed.py                 # verbatim CSV load + labelled synthetic augmentation
    smoke_test.py           # 22-check end-to-end demo flow test
    app/
      main.py, database.py, models.py
      routers/              # auth, dashboard, tasks, prediction, safety,
                            # behavior, training, incidents, history, assistant, admin
      services/
        safety_rules.py         # deterministic safety rules (no ML here)
        time_prediction.py      # GBM + honest LOO MAE + factor explanations
        behavior_analysis.py    # rules + z-scores + IsolationForest
        training_recommender.py # findings -> training modules
        simulator.py            # live simulated telemetry + event injection
        assistant.py            # intent-based grounded assistant
  frontend/
    src/pages/              # Dashboard, TaskDetail, SafetyMonitor,
                            # BehaviorAnalysis, TrainingHub, IncidentLog, History
    src/components/         # Layout (sidebar + critical banner), AssistantDrawer, ui
```

## How to run

Prerequisites: Python 3.10+, Node 18+.

```bash
# 1. Backend (http://localhost:8001, docs at /docs)
cd backend
pip install -r requirements.txt
python run.py

# 2. Frontend (http://localhost:5173, proxies /api -> :8001)
cd frontend
npm install
npm run dev

# 3. End-to-end smoke test (backend must be running)
cd backend
python smoke_test.py
```

### Demo logins

| Operator | PIN | Skill |
|---|---|---|
| OP1001 | 1001 | Intermediate |
| OP1002 | 1002 | Expert |
| OP1003 | 1003 | Beginner |

## 14-step demo workflow

1. Log in as **OP1001 / 1001**.
2. Dashboard shows machine status, safety posture, tasks D001–D004 and AI insights.
3. Open **D001 → Predict completion time**: predicted time, factor explanations
   ("why: rainy weather, machine age...") and the honest model disclaimer.
4. **Start operation** → Safety Monitor with live simulated sensors (2 s refresh).
5. **Simulate Seatbelt Violation** → instant CRITICAL alert (banner + sound), logged.
6. **Fasten Seatbelt**, then **Person Approaching (live)** → the distance closes
   every 2 s: a WARNING incident is logged first, then CRITICAL as the person
   crosses the weather-adjusted limits.
7. While the person is in the warning zone, switch **Environmental conditions**
   to **Fog** — the hazard thresholds enlarge (3.0 m → 4.5 m critical) and the
   alert **escalates to CRITICAL on its own**. Then **Clear Hazard**.
8. **Simulate Excessive Idling** → labelled telemetry rows are injected.
9. **Behavior Analysis** → finding card: what was detected, why it is unusual vs the
   operator baseline, and the recommended action.
10. **Training Hub** → "Efficient Idle Management" (TM-IDLE) is recommended because
    of the idling finding; assign it.
11. Mark the module **complete**.
12. Return to the task and **Complete task** → predicted vs actual with variance.
13. **History** → prediction accuracy, incidents by severity, data provenance.
14. Ask the **AI Assistant**: "Why am I flagged?", "Predict D002", "Am I safe?" —
    answers are grounded in live DB data.

To reset the demo: click **Reset demo data** in the sidebar (reseed DB + clears live
sessions), or `POST /api/admin/reseed` from Swagger UI at `/docs`.

## Assumptions & limitations

- Live telemetry, task "actual" times and instructor bookings are **simulated** and
  labelled as such; only the two supplied CSVs are real data.
- Actual completion time is generated near the prediction so the demo can show
  predicted-vs-actual variance within a short session.
- ML accuracy is limited by the 5-row supplied dataset; LOO MAE is disclosed, not
  hidden. Production use requires real CAT fleet historical data.
- Auth is a demo PIN (no hashing/JWT) — not for production.
- The AI assistant answers only from the app's own data; it has no general LLM
  knowledge and deliberately refuses to give safety overrides.

## Future enhancements

- Real telematics ingestion (CAT VisionLink / Product Link APIs).
- LLM-powered assistant with retrieval over manuals (RAG), still fenced off from
  safety rules.
- WebSocket push for sub-second alert latency; multi-site fleet view for supervisors.
- Model retraining pipeline with drift monitoring and per-site calibration.
- Shift-level fuel/idle cost analytics and CO2 reporting.

