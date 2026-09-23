"""Deterministic safety rule engine.

Safety-critical alerts are produced ONLY here, never by an LLM.
Working/operating conditions (weather, low light) tighten the thresholds.
"""
from datetime import datetime

# Proximity thresholds (metres) under normal conditions.
PROXIMITY_WARN_M = 6.0
PROXIMITY_CRITICAL_M = 3.0

# Working-condition multipliers: adverse conditions enlarge hazard zones.
CONDITION_FACTOR = {"Sunny": 1.0, "Cloudy": 1.1, "Rainy": 1.4, "Windy": 1.25,
                    "Fog": 1.5, "Night": 1.3}


def _factor(weather: str | None) -> float:
    return CONDITION_FACTOR.get((weather or "Sunny"), 1.0)


def evaluate_seatbelt(seatbelt_fastened: bool, engine_on: bool,
                      weather: str | None = None) -> dict | None:
    """Seatbelt unfastened while engine running -> CRITICAL, always."""
    if engine_on and not seatbelt_fastened:
        return {
            "incident_type": "Seatbelt Violation",
            "severity": "CRITICAL",
            "description": "Seatbelt unfastened while the machine engine is running. "
                           "Immediate stop-work condition under site safety policy.",
            "action_taken": "Operator alerted in-cab; supervisor notified; event logged.",
        }
    return None


def evaluate_proximity(distance_m: float, weather: str | None = None) -> dict | None:
    """Proximity hazard with working-condition-adjusted thresholds."""
    f = _factor(weather)
    warn, crit = PROXIMITY_WARN_M * f, PROXIMITY_CRITICAL_M * f
    if distance_m <= crit:
        return {
            "incident_type": "Proximity Hazard",
            "severity": "CRITICAL",
            "description": (f"Object/person detected {distance_m:.1f} m from machine "
                            f"(critical limit {crit:.1f} m under '{weather}' conditions)."),
            "action_taken": "Machine motion interlock warning issued; operator alerted.",
        }
    if distance_m <= warn:
        return {
            "incident_type": "Proximity Warning",
            "severity": "WARNING",
            "description": (f"Object within warning zone at {distance_m:.1f} m "
                            f"(warning limit {warn:.1f} m under '{weather}' conditions)."),
            "action_taken": "Visual/audible in-cab warning raised.",
        }
    return None


def evaluate_telemetry_row(row) -> dict | None:
    """Deterministic check of a Dataset-1 telemetry row."""
    return evaluate_seatbelt(row.seatbelt_status == "Fastened", engine_on=True)


def safety_summary(db, operator_id: str) -> dict:
    """Current safety posture for the dashboard."""
    from ..models import Incident
    open_incidents = (db.query(Incident)
                      .filter(Incident.operator_id == operator_id,
                              Incident.status != "Resolved")
                      .order_by(Incident.timestamp.desc()).all())
    critical = [i for i in open_incidents if i.severity == "CRITICAL"]
    return {
        "status": "CRITICAL" if critical else ("WARNING" if open_incidents else "SAFE"),
        "open_incidents": len(open_incidents),
        "critical_incidents": len(critical),
        "latest": [{
            "id": i.id, "type": i.incident_type, "severity": i.severity,
            "description": i.description, "status": i.status,
            "timestamp": i.timestamp.isoformat() if i.timestamp else None,
        } for i in open_incidents[:5]],
    }
