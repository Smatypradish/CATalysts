"""Simulated live telemetry for the hackathon demo.

Clearly SIMULATED data (the problem statement allows 'available or assumed
data'). Safety events are evaluated by the deterministic rule engine and every
safety event is written to the incident log.
"""
import random
from datetime import datetime, timedelta

from ..models import Incident, ScheduledTask, Telemetry
from . import safety_rules

_sessions: dict = {}  # operator_id -> live session state


def start_session(operator_id: str, machine_id: str, task_code: str,
                  weather: str) -> dict:
    _sessions[operator_id] = {
        "machine_id": machine_id, "task_code": task_code, "weather": weather,
        "rpm": 1450.0, "fuel_rate_lph": 12.5, "load_cycles": 0,
        "idle_seconds": 0, "seatbelt": True, "proximity_m": 12.0,
        "engine_on": True, "started": datetime.utcnow(),
        "forced_idle": False, "rng": random.Random(),
        "approach": False, "prox_level": None,
    }
    return snapshot(operator_id)


def get_live(operator_id: str) -> dict | None:
    return _sessions.get(operator_id)


def clear_sessions() -> None:
    """Drop all live sessions (used by the demo reseed endpoint)."""
    _sessions.clear()


def tick(db, operator_id: str) -> dict | None:
    """Advance the simulation one step (~2 s of machine time)."""
    s = _sessions.get(operator_id)
    if not s:
        return None
    rng = s["rng"]
    if not s["forced_idle"]:
        s["rpm"] = min(2200, max(700, s["rpm"] + rng.uniform(-120, 120)))
        if rng.random() < 0.30:
            s["load_cycles"] += 1
        s["idle_seconds"] += rng.choice([0, 0, 2])
    else:
        s["rpm"] = 750 + rng.uniform(-20, 20)   # idling RPM
        s["idle_seconds"] += 12                 # fast-forward idling for demo
    s["fuel_rate_lph"] = round(4 + s["rpm"] / 220, 1)
    if s["approach"]:
        # Person walking toward the machine: distance closes every tick.
        s["proximity_m"] = round(max(1.5, s["proximity_m"] - rng.uniform(0.7, 1.3)), 1)
    elif rng.random() < 0.05:  # benign proximity drift
        s["proximity_m"] = round(rng.uniform(7.0, 15.0), 1)

    alert = safety_rules.evaluate_seatbelt(s["seatbelt"], s["engine_on"], s["weather"])

    # Continuous proximity evaluation: log once per escalation level so the
    # demo shows WARNING first, then CRITICAL (and weather-driven escalation).
    prox_rule = safety_rules.evaluate_proximity(s["proximity_m"], s["weather"])
    new_level = prox_rule["severity"] if prox_rule else None
    if new_level != s["prox_level"]:
        if prox_rule:
            _log_incident(db, s, prox_rule, operator_id)
            alert = alert or prox_rule
        s["prox_level"] = new_level
    elif prox_rule and s["prox_level"] == "CRITICAL":
        alert = alert or prox_rule  # keep the critical alert visible while in zone
    return snapshot(operator_id, alert)


def snapshot(operator_id: str, active_alert: dict | None = None) -> dict | None:
    s = _sessions.get(operator_id)
    if not s:
        return None
    f = safety_rules.CONDITION_FACTOR.get(s["weather"], 1.0)
    return {
        "operator_id": operator_id,
        "machine_id": s["machine_id"], "task_code": s["task_code"],
        "weather": s["weather"], "engine_on": s["engine_on"],
        "rpm": round(s["rpm"]), "fuel_rate_lph": s["fuel_rate_lph"],
        "load_cycles": s["load_cycles"],
        "idle_minutes": round(s["idle_seconds"] / 60, 1),
        "seatbelt": "Fastened" if s["seatbelt"] else "Unfastened",
        "proximity_m": s["proximity_m"],
        "proximity_warn_m": round(safety_rules.PROXIMITY_WARN_M * f, 1),
        "proximity_critical_m": round(safety_rules.PROXIMITY_CRITICAL_M * f, 1),
        "condition_factor": f,
        "approaching": s["approach"],
        "elapsed_min": round((datetime.utcnow() - s["started"]).total_seconds() / 60, 1),
        "active_alert": active_alert,
        "simulated": True,
    }


def _log_incident(db, s, rule, operator_id) -> Incident:
    inc = Incident(timestamp=datetime.utcnow(), operator_id=operator_id,
                   machine_id=s["machine_id"], task_code=s["task_code"],
                   incident_type=rule["incident_type"], severity=rule["severity"],
                   description=rule["description"], status="Open",
                   action_taken=rule["action_taken"], source="simulated-sensor")
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def simulate_event(db, operator_id: str, event_type: str,
                   weather: str | None = None) -> dict:
    """Trigger a demo safety/behavior event. Safety events -> rule engine -> incident."""
    s = _sessions.get(operator_id)
    if not s:
        return {"ok": False, "error": "No active operation session. Start a task first."}

    if event_type == "weather_change":
        if weather not in safety_rules.CONDITION_FACTOR:
            return {"ok": False,
                    "error": f"Unknown weather '{weather}'. Options: "
                             f"{', '.join(safety_rules.CONDITION_FACTOR)}"}
        s["weather"] = weather
        # Re-evaluate proximity immediately: worsening conditions can escalate
        # an existing WARNING to CRITICAL (thresholds enlarge).
        rule = safety_rules.evaluate_proximity(s["proximity_m"], weather)
        new_level = rule["severity"] if rule else None
        inc_id = None
        if new_level != s["prox_level"]:
            if rule:
                inc_id = _log_incident(db, s, rule, operator_id).id
            s["prox_level"] = new_level
        return {"ok": True, "alert": rule if inc_id else None,
                "incident_id": inc_id, "snapshot": snapshot(operator_id, rule)}

    if event_type == "seatbelt_violation":
        s["seatbelt"] = False
        rule = safety_rules.evaluate_seatbelt(False, True, s["weather"])
        inc = _log_incident(db, s, rule, operator_id)
        return {"ok": True, "alert": rule, "incident_id": inc.id,
                "snapshot": snapshot(operator_id, rule)}
    if event_type == "seatbelt_fixed":
        s["seatbelt"] = True
        return {"ok": True, "alert": None, "snapshot": snapshot(operator_id)}
    if event_type == "proximity_hazard":
        s["proximity_m"] = 2.1
        rule = safety_rules.evaluate_proximity(2.1, s["weather"])
        inc = _log_incident(db, s, rule, operator_id)
        s["prox_level"] = rule["severity"]
        return {"ok": True, "alert": rule, "incident_id": inc.id,
                "snapshot": snapshot(operator_id, rule)}
    if event_type == "person_approaching":
        # Distance closes on every tick; rule engine logs WARNING then CRITICAL.
        s["proximity_m"] = min(s["proximity_m"], 9.5)
        s["approach"] = True
        return {"ok": True, "alert": None, "snapshot": snapshot(operator_id),
                "note": "Person approaching: distance closes each tick; WARNING "
                        "then CRITICAL fire as weather-adjusted thresholds cross."}
    if event_type == "proximity_clear":
        s["proximity_m"] = 12.0
        s["approach"] = False
        s["prox_level"] = None
        return {"ok": True, "alert": None, "snapshot": snapshot(operator_id)}

    if event_type in ("excessive_idling", "low_load", "fuel_anomaly"):
        s["forced_idle"] = event_type != "fuel_anomaly"
        _inject_behavior_rows(db, s, operator_id, event_type)
        return {"ok": True, "alert": None, "pattern_injected": event_type,
                "snapshot": snapshot(operator_id)}
    return {"ok": False, "error": f"Unknown event type: {event_type}"}


def _inject_behavior_rows(db, s, operator_id, pattern):
    """Add labelled simulated telemetry rows so the analyzer has something to find."""
    now = datetime.utcnow()
    if pattern == "excessive_idling":
        rows = [(now - timedelta(hours=3), 70, 4, 4.5),
                (now - timedelta(hours=1), 75, 3, 5.0)]
    elif pattern == "low_load":
        rows = [(now - timedelta(hours=2), 40, 1, 2.2),
                (now - timedelta(hours=1), 35, 2, 2.6)]
    else:  # fuel_anomaly
        rows = [(now - timedelta(hours=2), 20, 3, 12.8),
                (now - timedelta(hours=1), 25, 2, 14.1)]
    for ts, idle, cycles, fuel in rows:
        db.add(Telemetry(timestamp=ts, machine_id=s["machine_id"],
                         operator_id=operator_id, engine_hours=1535.0,
                         fuel_used=fuel, load_cycles=cycles, idling_time=float(idle),
                         seatbelt_status="Fastened", safety_alert_triggered="No",
                         proximity_m=None, source="simulated"))
    db.commit()


def end_session(db, operator_id: str) -> dict:
    """Stop the live session; return elapsed minutes (simulated actual time)."""
    s = _sessions.pop(operator_id, None)
    if not s:
        return {"ok": False}
    elapsed = (datetime.utcnow() - s["started"]).total_seconds() / 60
    return {"ok": True, "elapsed_min": round(elapsed, 1),
            "load_cycles": s["load_cycles"], "idle_minutes": round(s["idle_seconds"] / 60, 1)}


def active_task(db, operator_id: str) -> ScheduledTask | None:
    return (db.query(ScheduledTask)
            .filter(ScheduledTask.operator_id == operator_id,
                    ScheduledTask.status == "In Progress").first())
