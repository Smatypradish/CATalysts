# CAT Operator Companion

An intelligent operator assistant for CAT machinery, built for the hackathon problem
statement. It combines task-time prediction, a deterministic real-time safety rule
engine, unusual behavior detection, behaviour-linked training recommendations and a
grounded rule-based assistant — in one operator-facing web app.

## Problem

Heavy-equipment operators juggle task scheduling, safety compliance and fuel/idle
efficiency. Supervisors lack real-time visibility into unsafe behavior, and training
assignments are generic instead of tied to observed behavior. The companion gives the
operator a single dashboard that predicts task durations, watches safety sensors in
real time, detects unusual operating behavior, and recommends targeted training.

## Solution overview

| Capability | How it works |
|---|---|
| Operator dashboard | Live status of machine, safety posture, today's tasks, data-driven insights |
| Task time prediction | scikit-learn `GradientBoostingRegressor` + `OneHotEncoder(task_type, weather, skill)` + machine age; counterfactual factor explanations |
| What-If Simulator | Baseline vs what-if side-by-side over task type, weather, skill, machine age (same prediction model) + workload/idle (documented simulated layer); shows duration, estimated fuel, operating outcome band, absolute/% differences and top factors with model-vs-simulated provenance labels |
| Real-time safety monitoring | **Deterministic rule engine only** (seatbelt, proximity) with weather-adjusted thresholds; CRITICAL alerts fire instantly and are logged. Dynamic Proximity Safety Zone: simulated machine speed + radar readings give relative closing speed and time-to-contact, classifying surroundings SAFE / CAUTION / DANGER with an in-UI zone graphic and browser voice alerts (speech synthesis) |
| Unusual behavior detection | Policy rules + per-operator z-scores vs baseline + `IsolationForest` outliers; every finding explains *what / why / action* |
| Training recommendations | Findings are mapped to training modules (e.g. excessive idling → TM-IDLE) — derived from data, not hardcoded |
| Smart assistant | Rule-based (not an LLM): intent-classified, grounded answers over the app's own data (safety status, predictions, behavior findings). Not an open chatbot — answers always cite the data they used |
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
  machine age, estimated vs actual time. Loaded verbatim (`source="dataset"`) and
  never modified.
- `data/task_records_100.csv` (100 rows) — the expanded task-time training set: the
  same 5 Caterpillar rows embedded unchanged (`source="dataset"`) plus 95
  clearly-labelled synthetic rows (`source="synthetic"`, Task IDs S001–S095).
  Produced by `backend/generate_task_records_100.py` — a documented, deterministic
  (seeded) formula with realistic noise; re-running it regenerates the identical file
  and self-verifies that the 5 originals match the supplied CSV exactly.

### Small-dataset honesty

5 rows cannot train a reliable regressor, so the model is augmented with 95 labelled
synthetic rows (`source="synthetic"`; generation formula documented in
`backend/generate_task_records_100.py`) for 100 training records in total.
`Estimated Time` is deliberately **not** a model input (it is a planner guess, not a
physical driver of duration). Validation is reported honestly, never as a percentage:
an 80/20 seeded split of the 95 synthetic rows yields a holdout MAE/RMSE, and
separately a leave-one-out MAE over the 5 real rows shows how predictions behave on
the supplied data — explicitly labelled a very small prototype evaluation, not
production accuracy. These numbers are disclosed in every prediction response and in
the UI footer. All simulated telemetry is tagged `source="simulated"` and shown with
badges in the UI.

## Project structure

```
CAT-Operator-Companion/
  data/                     # supplied CSVs (untouched) + expanded 100-row dataset
  backend/
    run.py                  # start server (seeds DB + trains model on boot)
    seed.py                 # verbatim CSV loads + provenance integrity check
    generate_task_records_100.py  # documented generator: 5 originals + 95 synthetic
    smoke_test.py           # 40-check end-to-end demo flow + dataset/zone/what-if integrity test
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
        what_if.py              # baseline vs what-if: model reuse + documented
                                # simulated fuel/workload layer (NOT CAT formulas)
        assistant.py            # intent-based grounded assistant
  frontend/
    src/pages/              # Dashboard, TaskDetail, SafetyMonitor,
                            # BehaviorAnalysis, TrainingHub, IncidentLog, History,
                            # WhatIfSimulator
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

Every operator has their own machine and scheduled tasks, so you can switch logins
mid-demo: OP1001 → EXC001 (tasks D001–D004), OP1002 → EXC002 (D005–D007),
OP1003 → LOD001 (D008–D010).

## 14-step demo workflow

1. Log in as **OP1001 / 1001**.
2. Dashboard shows machine status, safety posture, tasks D001–D004 and smart insights.
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
14. Ask the **Smart Assistant**: "Why am I flagged?", "Predict D002", "Am I safe?" —
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

## Limitations & Judge Q&A

### What is real vs synthetic vs simulated

| Data | Source tag | What it is |
|---|---|---|
| `data/machine_telemetry.csv` (4 rows) | `dataset` | Supplied Dataset 1, loaded verbatim |
| `data/task_records.csv` (5 rows) | `dataset` | Supplied Dataset 2, loaded verbatim; never modified |
| 95 task-history rows in `data/task_records_100.csv` | `synthetic` | Labelled prototype rows from a documented, deterministic formula (`backend/generate_task_records_100.py`); the file also embeds the 5 originals unchanged |
| Baseline + live telemetry rows | `simulated` | Generated sensor data for operator baselines and the live demo; always labelled |
| Operators, machines, scheduled tasks, training modules | demo master data | Seeded demo content, not from any dataset |

### Honest limitations

- **The assistant is deterministic/rule-based, not an LLM.** It classifies intent with
  keyword matching and answers from templates grounded in live database queries,
  always citing the data it used. We chose this deliberately: it cannot hallucinate
  and can never override or silence a safety rule. An LLM+RAG layer over CAT manuals
  is future work (with safety intents still hard-blocked).
- **Task-time prediction** trains on 100 task-history records: the 5 supplied real
  Caterpillar records plus 95 clearly-labelled synthetic prototype records
  (`data/task_records_100.csv`). `Estimated Time` is not a model input. We do **not**
  claim production-level ML accuracy and report no percentage accuracy: an 80/20
  holdout MAE/RMSE over the synthetic rows and a leave-one-out MAE over the 5 real
  rows (a very small prototype evaluation) are disclosed in the UI and every
  prediction response, with an explicit non-production disclaimer.
- **Proximity and movement telemetry is simulated/assumed.** The supplied dataset
  has no proximity sensor or machine-speed field, so proximity distance, relative
  closing speed and ground speed are assumed sensors for the prototype
  (documented in
  `backend/app/models.py`); the deterministic rule logic is what would run on real
  sensor feeds.
- **Task completion "actual" times are simulated** for demo acceleration (scaled near
  the prediction) so predicted-vs-actual variance can be shown within a short
  session; this is disclosed in the API response and the UI.
- **Authentication is demo-scope PIN login** (no hashing, tokens or roles) — it is
  not production authentication.
- **What-If fuel/workload model is simulated**: predicted duration comes from the
  trained task-time model, but the workload/idle duration transform, fuel burn
  (15 L/h productive at 100% workload, 4 L/h idling) and outcome bands are simple
  documented prototype assumptions in `backend/app/services/what_if.py` — **not**
  real CAT operational formulas. The UI tags every value ML (model-predicted) or
  SIM (simulated).
- **Real deployment** would use real CAT fleet telemetry (VisionLink / Product Link),
  real proximity sensors, enterprise identity/authentication, and production-grade
  infrastructure.

## Future enhancements

- Real telematics ingestion (CAT VisionLink / Product Link APIs).
- LLM-powered assistant with retrieval over manuals (RAG), still fenced off from
  safety rules.
- WebSocket push for sub-second alert latency; multi-site fleet view for supervisors.
- Model retraining pipeline with drift monitoring and per-site calibration.
- Shift-level fuel/idle cost analytics and CO2 reporting.

