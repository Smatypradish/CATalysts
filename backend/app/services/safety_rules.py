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

# Dynamic zone: time-to-contact thresholds (seconds). A fast-closing object is
# hazardous even outside the static distance radii, so the zone classification
# also considers time-to-contact = distance / closing_speed. Pure deterministic
# arithmetic on sensor inputs — no ML, no LLM.
TTC_CAUTION_S = 10.0
TTC_DANGER_S = 4.0


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


def relative_closing_speed_mps(prev_distance_m: float | None,
                               distance_m: float,
                               dt_seconds: float) -> float | None:
    """Relative closing speed between two proximity readings (m/s).

    Positive = object and machine are approaching each other, negative =
    separating, None = not computable (no previous reading / no time elapsed).
    """
    if prev_distance_m is None or dt_seconds <= 0:
        return None
    return (prev_distance_m - distance_m) / dt_seconds


def classify_zone(distance_m: float, weather: str | None = None,
                  closing_speed_mps: float | None = None) -> dict:
    """Classify the machine surroundings as SAFE / CAUTION / DANGER.

    Deterministic: combines the weather-adjusted static radii with the
    time-to-contact (TTC) of a closing object. DANGER when inside the critical
    radius or contact is imminent; CAUTION when inside the warning radius or
    closing fast enough to reach the machine soon; otherwise SAFE.
    """
    f = _factor(weather)
    warn, crit = PROXIMITY_WARN_M * f, PROXIMITY_CRITICAL_M * f
    ttc = (distance_m / closing_speed_mps
           if closing_speed_mps and closing_speed_mps > 0 else None)
    if distance_m <= crit:
        zone, reason = "DANGER", (f"inside critical radius "
                                  f"({distance_m:.1f} m <= {crit:.1f} m)")
    elif ttc is not None and ttc <= TTC_DANGER_S:
        zone, reason = "DANGER", (f"closing at {closing_speed_mps:.1f} m/s, "
                                  f"contact in ~{ttc:.1f} s")
    elif distance_m <= warn:
        zone, reason = "CAUTION", (f"inside warning radius "
                                   f"({distance_m:.1f} m <= {warn:.1f} m)")
    elif ttc is not None and ttc <= TTC_CAUTION_S:
        zone, reason = "CAUTION", (f"closing at {closing_speed_mps:.1f} m/s, "
                                   f"contact in ~{ttc:.1f} s")
    else:
        zone, reason = "SAFE", "outside all hazard zones"
    return {
        "zone": zone,
        "distance_m": round(distance_m, 1),
        "warn_m": round(warn, 1),
        "crit_m": round(crit, 1),
        "condition_factor": f,
        "closing_speed_mps": (round(closing_speed_mps, 2)
                              if closing_speed_mps is not None else None),
        "ttc_s": round(ttc, 1) if ttc is not None else None,
        "reason": reason,
    }


def evaluate_dynamic_proximity(distance_m: float, weather: str | None = None,
                               closing_speed_mps: float | None = None
                               ) -> dict | None:
    """Zone-aware proximity alert: DANGER -> CRITICAL, CAUTION -> WARNING.

    Same incident types/severities as the static rule, enriched with closing
    speed / time-to-contact context. Returns None when the zone is SAFE.
    """
    z = classify_zone(distance_m, weather, closing_speed_mps)
    if z["zone"] == "SAFE":
        return None
    closing = ""
    if z["closing_speed_mps"]:
        closing = (f" Closing speed {z['closing_speed_mps']:.1f} m/s"
                   f" (contact in ~{z['ttc_s']} s).")
    if z["zone"] == "DANGER":
        return {
            "incident_type": "Proximity Hazard",
            "severity": "CRITICAL",
            "description": (f"Object/person detected {distance_m:.1f} m from machine — "
                            f"DANGER zone ({z['reason']}; critical limit "
                            f"{z['crit_m']:.1f} m under '{weather}' conditions)."
                            + closing),
            "action_taken": "Machine motion interlock warning issued; operator alerted.",
            "zone": z,
        }
    return {
        "incident_type": "Proximity Warning",
        "severity": "WARNING",
        "description": (f"Object within caution zone at {distance_m:.1f} m "
                        f"({z['reason']}; warning limit {z['warn_m']:.1f} m "
                        f"under '{weather}' conditions)." + closing),
        "action_taken": "Visual/audible in-cab warning raised.",
        "zone": z,
    }


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
