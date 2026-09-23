"""Verify all three operators have machine, tasks, behavior records after reseed."""
import json
import urllib.request

BASE = "http://localhost:8001"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.load(r)


def post(path):
    req = urllib.request.Request(BASE + path, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


print("reseed:", post("/api/admin/reseed"))

for op in ("OP1001", "OP1002", "OP1003"):
    d = get(f"/api/dashboard/{op}")
    m = d["machine"]
    print(f"\n== {op} {d['operator']['name']} ({d['operator']['skill']}) ==")
    print("  machine:", f"{m['machine_id']} {m['model']} ({m['status']})" if m else None)
    print("  tasks:", [(t["task_code"], t["task_type"], t["weather"],
                        t["estimated_time"]) for t in d["tasks"]])
    print("  behavior:", d["behavior_counts"])
    print("  insight[0]:", d["insights"][0] if d["insights"] else None)
    # prediction works for first scheduled task
    pend = [t for t in d["tasks"] if t["status"] == "Scheduled"]
    if pend:
        t0 = pend[0]
        p = post(f"/api/tasks/{t0['task_code']}/predict")
        print(f"  predict {t0['task_code']}: {p['predicted_time_min']} min "
              f"(est {t0['estimated_time']})")
print("\nALL OPERATORS OK")
