"""End-to-end demo workflow smoke test against a running server on :8001."""
import csv
import json
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:8001"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=15) as r:
        return json.loads(r.read())


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name


# 1. Login
me = call("POST", "/api/auth/login", {"operator_id": "OP1001", "pin": "1001"})
check("login", me["operator_id"] == "OP1001")

# 2. Dashboard shows today's tasks
dash = call("GET", "/api/dashboard/OP1001")
check("dashboard tasks", len(dash["tasks"]) == 4)
check("insights present", len(dash["insights"]) >= 1)

# 3-4. Select a task and predict completion time
pred = call("POST", "/api/tasks/D001/predict")
check("prediction returned", pred["predicted_time_min"] > 0)
check("factors explained", len(pred["factors"]) >= 1)
print("   predicted", pred["predicted_time_min"], "min | model MAE",
      pred["model"]["loo_mae_real_rows_min"])

# 5. Start operation (starts simulated live session)
started = call("POST", "/api/tasks/D001/start")
check("task in progress", started["task"]["status"] == "In Progress")
live = call("GET", "/api/safety/live/OP1001")
check("live session active", live["active"] is True)

# 6-8. Seatbelt violation -> immediate CRITICAL alert + incident logged
ev = call("POST", "/api/safety/simulate",
          {"operator_id": "OP1001", "event_type": "seatbelt_violation"})
check("seatbelt CRITICAL alert", ev["alert"]["severity"] == "CRITICAL")
incs = call("GET", "/api/incidents?operator_id=OP1001")
check("incident logged", any(i["incident_type"] == "Seatbelt Violation"
                             and i["severity"] == "CRITICAL" for i in incs))
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "seatbelt_fixed"})

# Proximity hazard -> immediate alert + incident
ev2 = call("POST", "/api/safety/simulate",
           {"operator_id": "OP1001", "event_type": "proximity_hazard"})
check("proximity alert", ev2["alert"]["incident_type"] == "Proximity Hazard")
incs = call("GET", "/api/incidents?operator_id=OP1001")
check("proximity incident logged",
      any(i["incident_type"] == "Proximity Hazard" for i in incs))
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "proximity_clear"})

# Dynamic Proximity Safety Zone: movement telemetry + SAFE/CAUTION/DANGER
live = call("GET", "/api/safety/live/OP1001")
check("zone + movement fields present (labelled simulated)",
      live["zone"] == "SAFE" and live["speed_kmh"] is not None
      and live["movement_simulated"] is True)

# Person walking up: SAFE -> CAUTION (WARNING) -> DANGER (CRITICAL)
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "person_approaching"})
seen_zones, danger_at = set(), None
for _ in range(20):
    live = call("GET", "/api/safety/live/OP1001")
    seen_zones.add(live["zone"])
    if live["zone"] == "DANGER":
        danger_at = live["proximity_m"]
        break
incs = call("GET", "/api/incidents?operator_id=OP1001")
check("person approach: CAUTION zone before DANGER (WARNING logged first)",
      "CAUTION" in seen_zones and "DANGER" in seen_zones
      and any(i["incident_type"] == "Proximity Warning"
              and i["severity"] == "WARNING" for i in incs))
check("person approach: DANGER escalation (CRITICAL logged)",
      danger_at is not None
      and any(i["incident_type"] == "Proximity Hazard"
              and i["severity"] == "CRITICAL" for i in incs))
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "proximity_clear"})

# Weather adjustment enlarges the deterministic hazard zones
w = call("POST", "/api/safety/simulate",
         {"operator_id": "OP1001", "event_type": "weather_change",
          "weather": "Rainy"})
check("weather adjustment: Rainy enlarges zones (8.4 m / 4.2 m)",
      w["snapshot"]["proximity_warn_m"] == 8.4
      and w["snapshot"]["proximity_critical_m"] == 4.2)
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "weather_change",
      "weather": "Sunny"})

# Fast-approaching vehicle: time-to-contact drives the zone into CAUTION
# while still OUTSIDE the static 6 m warning radius (dynamic zone proof).
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "vehicle_approaching"})
live = call("GET", "/api/safety/live/OP1001")
check("dynamic zone: TTC-driven CAUTION beyond static warning radius",
      live["zone"] in ("CAUTION", "DANGER")
      and live["proximity_m"] > live["proximity_warn_m"]
      and live["closing_speed_mps"] > 0)
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "proximity_clear"})
live = call("GET", "/api/safety/live/OP1001")
check("zone returns to SAFE after hazard clears", live["zone"] == "SAFE")

# 9-11. Inject excessive idling -> analyzer detects + explains
call("POST", "/api/safety/simulate",
     {"operator_id": "OP1001", "event_type": "excessive_idling"})
ana = call("GET", "/api/behavior/OP1001/analyze")
codes = {f["code"] for f in ana["findings"]}
check("excessive idling detected", "EXCESSIVE_IDLING" in codes)
check("findings explain why+action",
      all(f["why"] and f["action"] for f in ana["findings"]))

# 12-13. Training recommendations linked to behavior
check("training recs linked", len(ana["training_recommendations"]) >= 1)
idle_rec = [r for r in ana["training_recommendations"]
            if r["triggered_by"] == "EXCESSIVE_IDLING"]
check("idling -> idle module", idle_rec and
      idle_rec[0]["module_code"] == "TM-IDLE")
asg = call("POST", "/api/training/assign",
           {"operator_id": "OP1001", "module_code": "TM-IDLE",
            "reason": idle_rec[0]["reason"]})
check("module assigned", asg["status"] == "Assigned")

# 14. Complete task -> predicted vs actual
time.sleep(2)
done = call("POST", "/api/tasks/D001/complete", {})
check("task completed", done["task"]["status"] == "Completed")
check("variance computed", done["variance_min"] is not None)
perf = call("GET", "/api/history/OP1001/performance")
check("performance history", len(perf["completed_tasks"]) == 1)

# Expanded training dataset: 100 records = 5 original (verbatim) + 95 synthetic.
hist = perf["historical_records"]
check("100 total training records", len(hist) == 100)
n_ds = sum(1 for r in hist if r["source"] == "dataset")
n_sy = sum(1 for r in hist if r["source"] == "synthetic")
check("provenance: 5 dataset + 95 synthetic", n_ds == 5 and n_sy == 95)

# The 5 Caterpillar-supplied rows must be exactly the supplied CSV values.
supplied = sorted(csv.DictReader((DATA_DIR / "task_records.csv").open()),
                  key=lambda r: r["Task ID"])
orig = sorted((r for r in hist if r["source"] == "dataset"),
              key=lambda r: r["task_id"])
check("original 5 rows unchanged", len(supplied) == 5 and len(orig) == 5 and all(
    o["Task ID"] == d["task_id"] and o["Task Type"] == d["task_type"]
    and o["Weather"] == d["weather"] and o["Operator Skill"] == d["operator_skill"]
    and float(o["Machine Age (yrs)"]) == float(d["machine_age"])
    and float(o["Estimated Time (min)"]) == float(d["estimated_time"])
    and float(o["Actual Time (min)"]) == float(d["actual_time"])
    for o, d in zip(supplied, orig)))

# Honest model metadata: validation split + no estimated-time feature leakage.
mi = call("GET", "/api/prediction/model-info")
check("validation split covers the 95 synthetic rows",
      mi["n_synth_train"] + mi["n_synth_validation"] == 95)
check("synthetic holdout MAE reported",
      mi["synth_validation_mae_min"] is not None)
check("estimated time NOT a model feature",
      "estimated_time" not in mi["features"])
print("   model eval:", mi["evaluation_note"])

# Assistant answers from app data
a1 = call("POST", "/api/assistant/ask",
          {"operator_id": "OP1001", "message": "Why was my behavior flagged?"})
check("assistant behavior answer", "idling" in a1["answer"].lower())
a2 = call("POST", "/api/assistant/ask",
          {"operator_id": "OP1001", "message": "How long will my next task take?"})
check("assistant prediction answer", "min" in a2["answer"])

# What-If Simulator: options, baseline vs what-if, provenance
wio = call("GET", "/api/prediction/what-if/options")
check("what-if options from model encoder",
      len(wio["task_types"]) == 5 and len(wio["weathers"]) == 4
      and len(wio["skills"]) == 3)

wi_base = {"task_type": "Earth Excavation", "weather": "Sunny",
           "operator_skill": "Intermediate", "machine_age": 5,
           "workload_pct": 100, "idle_pct": 10}
same = call("POST", "/api/prediction/what-if",
            {"baseline": wi_base, "scenario": dict(wi_base)})
check("identical scenarios -> zero diff",
      same["comparison"]["duration"]["abs_diff"] == 0
      and same["comparison"]["duration"]["pct_diff"] == 0
      and same["comparison"]["fuel"]["abs_diff"] == 0)

worse_in = {"task_type": "Earth Excavation", "weather": "Rainy",
            "operator_skill": "Beginner", "machine_age": 9,
            "workload_pct": 120, "idle_pct": 30}
worse = call("POST", "/api/prediction/what-if",
             {"baseline": wi_base, "scenario": worse_in})
check("what-if worsens duration + fuel + outcome",
      worse["comparison"]["duration"]["abs_diff"] > 0
      and worse["comparison"]["fuel"]["abs_diff"] > 0
      and worse["scenario"]["outcome"]["level"] in ("MEDIUM", "HIGH"))
check("percentage difference reported",
      worse["comparison"]["duration"]["pct_diff"] > 0
      and worse["comparison"]["fuel"]["pct_diff"] > 0)

# Model vs simulated separation: change ONLY workload/idle -> the
# model-predicted duration must be identical while totals differ.
sim_only = call("POST", "/api/prediction/what-if",
                {"baseline": wi_base,
                 "scenario": {**wi_base, "workload_pct": 80, "idle_pct": 40}})
check("workload/idle do not change the model prediction",
      sim_only["comparison"]["model_duration"]["abs_diff"] == 0
      and sim_only["comparison"]["duration"]["abs_diff"] != 0)

check("top factors attributed with provenance",
      len(worse["comparison"]["top_factors"]) >= 1 and all(
          f["source"] in ("model", "simulated")
          for f in worse["comparison"]["top_factors"]))
check("assumptions + provenance documented in response",
      "assumptions" in worse["provenance"]
      and "NOT real CAT" in worse["provenance"]["simulated"])
print("   what-if:", wi_base["task_type"], "baseline",
      worse["comparison"]["duration"]["baseline"], "min ->",
      worse["comparison"]["duration"]["scenario"], "min (",
      worse["comparison"]["duration"]["pct_diff"], "% )")

print("\nALL SMOKE TESTS PASSED")
