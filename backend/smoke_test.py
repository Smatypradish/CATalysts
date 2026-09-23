"""End-to-end demo workflow smoke test against a running server on :8001."""
import json
import time
import urllib.request

BASE = "http://localhost:8001"


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

# Assistant answers from app data
a1 = call("POST", "/api/assistant/ask",
          {"operator_id": "OP1001", "message": "Why was my behavior flagged?"})
check("assistant behavior answer", "idling" in a1["answer"].lower())
a2 = call("POST", "/api/assistant/ask",
          {"operator_id": "OP1001", "message": "How long will my next task take?"})
check("assistant prediction answer", "min" in a2["answer"])

print("\nALL SMOKE TESTS PASSED")
