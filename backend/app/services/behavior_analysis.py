"""Unusual behavior detection: rules + statistics + IsolationForest.

Every finding is explainable: what was detected, why it is unusual
(vs the operator's own baseline and fleet rules) and what action is
recommended. Findings map to training modules.
"""
import pandas as pd
from sklearn.ensemble import IsolationForest

from ..models import Telemetry

IDLE_RULE_MIN = 45          # minutes in a single record window
LOW_LOAD_RULE = 2           # cycles in a record window
FUEL_PER_CYCLE_Z = 1.5      # z-score threshold vs operator baseline
REPEAT_VIOLATION_RULE = 2   # unfastened/alert records


def analyze(db, operator_id: str) -> dict:
    rows = (db.query(Telemetry).filter(Telemetry.operator_id == operator_id)
            .order_by(Telemetry.timestamp).all())
    if not rows:
        return {"operator_id": operator_id, "records": 0, "findings": [], "baseline": {}}

    df = pd.DataFrame([{
        "timestamp": r.timestamp, "machine_id": r.machine_id,
        "engine_hours": r.engine_hours, "fuel_used": r.fuel_used,
        "load_cycles": r.load_cycles, "idling_time": r.idling_time,
        "seatbelt": r.seatbelt_status, "alert": r.safety_alert_triggered,
        "source": r.source,
    } for r in rows])
    df["fuel_per_cycle"] = df["fuel_used"] / df["load_cycles"].clip(lower=1)

    baseline = {
        "avg_idling_min": round(float(df.idling_time.mean()), 1),
        "avg_load_cycles": round(float(df.load_cycles.mean()), 1),
        "avg_fuel_per_cycle": round(float(df.fuel_per_cycle.mean()), 2),
        "records": len(df),
        "dataset_records": int((df.source == "dataset").sum()),
        "simulated_records": int((df.source == "simulated").sum()),
    }
    fpc_mean = df.fuel_per_cycle.mean()
    fpc_std = df.fuel_per_cycle.std(ddof=0) or 1e-6
    idle_mean = df.idling_time.mean()
    idle_std = df.idling_time.std(ddof=0) or 1e-6

    findings = []

    def add(code, title, severity, detected, why, action, module, evidence):
        findings.append({"code": code, "title": title, "severity": severity,
                         "detected": detected, "why": why, "action": action,
                         "recommended_module": module, "evidence": evidence})

    # --- 1. Excessive idling (policy rule + z-score vs operator baseline) ---
    for _, r in df.iterrows():
        z = (r.idling_time - idle_mean) / idle_std
        if r.idling_time >= IDLE_RULE_MIN:
            add("EXCESSIVE_IDLING", "Excessive idling", "HIGH",
                f"{r.timestamp:%Y-%m-%d %H:%M} on {r.machine_id}: {r.idling_time:.0f} min idling.",
                f"Above the {IDLE_RULE_MIN} min policy limit and {z:+.1f} sigma vs the "
                f"operator's average of {baseline['avg_idling_min']} min. Idling burns fuel "
                f"with zero productive work.",
                "Plan work cycles to avoid standby running; use auto-shutdown; review shift plan.",
                "TM-IDLE",
                {"idling_min": float(r.idling_time), "z_score": round(float(z), 2)})

    # --- 2. Low load activity ---
    for _, r in df.iterrows():
        if r.load_cycles <= LOW_LOAD_RULE:
            add("LOW_LOAD", "Low load activity", "MEDIUM",
                f"{r.timestamp:%Y-%m-%d %H:%M} on {r.machine_id}: only {r.load_cycles} load cycle(s).",
                f"Operator baseline is {baseline['avg_load_cycles']} cycles per window; "
                f"<= {LOW_LOAD_RULE} cycles means the machine ran nearly empty - waiting, "
                f"poor task allocation or inefficient technique.",
                "Check task allocation; combine with idling data; coach on work-cycle planning.",
                "TM-IDLE",
                {"load_cycles": int(r.load_cycles), "baseline": baseline["avg_load_cycles"]})

    # --- 3. Unusual fuel usage (z-score on fuel per productive cycle) ---
    for _, r in df.iterrows():
        z = (r.fuel_per_cycle - fpc_mean) / fpc_std
        if abs(z) >= FUEL_PER_CYCLE_Z:
            direction = "high" if z > 0 else "low"
            add("FUEL_ANOMALY", "Unusual fuel usage", "MEDIUM",
                f"{r.timestamp:%Y-%m-%d %H:%M} on {r.machine_id}: {r.fuel_used} L for "
                f"{r.load_cycles} cycle(s) = {r.fuel_per_cycle:.2f} L/cycle.",
                f"Fuel-per-cycle is {z:+.1f} sigma vs operator mean {fpc_mean:.2f} L/cycle. "
                f"Abnormally {direction} fuel per unit of work suggests inefficient operation "
                f"or unlogged activity.",
                "Review operating technique; check machine health; consider fuel-efficiency "
                "training.", "TM-FUEL",
                {"fuel_per_cycle": round(float(r.fuel_per_cycle), 2),
                 "z_score": round(float(z), 2)})
    return _finish(db, df, operator_id, baseline, findings, add)


def _finish(db, df, operator_id, baseline, findings, add) -> dict:
    # --- 4. Seatbelt / safety violations (deterministic) ---
    viol = df[(df.seatbelt == "Unfastened") | (df.alert == "Yes")]
    for _, r in viol.iterrows():
        add("SAFETY_VIOLATION", "Unsafe operation: seatbelt/alert record", "HIGH",
            f"{r.timestamp:%Y-%m-%d %H:%M} on {r.machine_id}: seatbelt "
            f"{r.seatbelt}, safety alert {r.alert}.",
            "Operating unbelted with an active safety alert is a direct violation of site "
            "safety policy and correlates with incident risk.",
            "Immediate coaching; assign seatbelt-safety module; supervisor review.",
            "TM-SEATBELT",
            {"seatbelt": r.seatbelt, "alert": r.alert})
    if len(viol) >= REPEAT_VIOLATION_RULE:
        add("REPEAT_VIOLATIONS", "Repeated safety violations", "CRITICAL",
            f"{len(viol)} records with unfastened seatbelt and/or triggered safety alert.",
            f"Policy allows 0 violations; {len(viol)} occurrences form a pattern, not a "
            f"one-off lapse.",
            "Mandatory seatbelt + safe-operation retraining before next shift; flag to "
            "safety officer.", "TM-SEATBELT",
            {"violation_records": int(len(viol))})

    # --- 5. IsolationForest: multivariate outliers (supporting evidence) ---
    ml_outliers = []
    if len(df) >= 6:
        feats = df[["idling_time", "load_cycles", "fuel_used", "engine_hours"]].astype(float)
        iso = IsolationForest(contamination=0.15, random_state=42).fit(feats)
        df["iso"] = iso.predict(feats)
        df["iso_score"] = iso.decision_function(feats)
        for _, r in df[df.iso == -1].iterrows():
            ml_outliers.append({
                "timestamp": r.timestamp.isoformat(),
                "idling_min": float(r.idling_time), "load_cycles": int(r.load_cycles),
                "fuel_used": float(r.fuel_used),
                "anomaly_score": round(float(r.iso_score), 3)})

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: severity_rank.get(f["severity"], 9))
    return {
        "operator_id": operator_id, "records": len(df), "baseline": baseline,
        "findings": findings, "ml_outliers": ml_outliers,
        "method": ("Deterministic policy rules + per-operator z-scores vs baseline + "
                   "IsolationForest (multivariate outlier confirmation). All findings "
                   "include what/why/action explanations."),
    }
