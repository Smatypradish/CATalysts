"""What-If Simulator service — baseline vs scenario comparison.

REUSES the existing task-time prediction pipeline (time_prediction.predict)
unchanged: task_type, weather, operator_skill and machine_age are the exact
model features, so the predicted duration for BOTH the baseline and the
what-if scenario comes from the same trained GradientBoosting model used on
the Task Detail page. No retraining, no dataset changes, no new model.

Workload and Idle Time are deliberately NOT model inputs (they are not in the
supplied training data), so they are applied as a clearly-labelled SIMULATED
adjustment layer on top of the model prediction.

=====================================================================
SIMULATED PROTOTYPE MODEL — DOCUMENTED ASSUMPTIONS (NOT real CAT formulas)
=====================================================================
These are simple, transparent prototype heuristics chosen for demo
plausibility only. They are NOT Caterpillar engineering data:

  PRODUCTIVE_BURN_L_H = 15.0  assumed fuel burn while productively working at
                              100% workload; scales LINEARLY with workload.
  IDLE_BURN_L_H       = 4.0   assumed fuel burn per hour while idling.

  productive_min  = model_predicted_min * 100 / workload_pct
      (linear productivity assumption: at 120% workload the same productive
      work finishes in 100/120 of the time)
  total_clock_min = productive_min / (1 - idle_pct/100)
  fuel_l          = productive_h * PRODUCTIVE_BURN_L_H * workload_pct/100
                  + idle_h * IDLE_BURN_L_H

Operating outcome bands (deterministic prototype heuristics):
  workload_pct > 110  -> OVERLOAD RISK   (HIGH)
  idle_pct > 25       -> HIGH IDLE WASTE (MEDIUM)
  workload_pct < 60   -> UNDERUTILIZED   (MEDIUM)
  otherwise           -> NORMAL          (LOW)
=====================================================================

Change attribution ("top factors") telescopes the total difference into
model layer -> workload -> idle, so contributions sum exactly to the total
duration change. The model layer is decomposed one input at a time
(marginal; interactions ignored — documented limitation). Each factor is
tagged source="model" or source="simulated" for provenance in the UI.
"""
from . import time_prediction

# --- Documented prototype assumptions (NOT real CAT operational formulas) ---
PRODUCTIVE_BURN_L_H = 15.0   # assumed L/h at 100% workload, scales linearly
IDLE_BURN_L_H = 4.0          # assumed L/h while idling
WORKLOAD_MIN, WORKLOAD_MAX = 40, 130     # % of nominal workload
IDLE_MIN, IDLE_MAX = 0, 60               # % of clock time spent idling
OVERLOAD_PCT = 110.0
HIGH_IDLE_PCT = 25.0
UNDERUTILIZED_PCT = 60.0

ASSUMPTIONS = {
    "productive_burn_l_h_at_100pct_workload": PRODUCTIVE_BURN_L_H,
    "idle_burn_l_h": IDLE_BURN_L_H,
    "workload_effect": "productive_min = model_min * 100 / workload_pct (linear)",
    "idle_effect": "total_clock_min = productive_min / (1 - idle_pct/100)",
    "outcome_bands": {
        "overload_risk": f"workload > {OVERLOAD_PCT:g}%",
        "high_idle_waste": f"idle > {HIGH_IDLE_PCT:g}%",
        "underutilized": f"workload < {UNDERUTILIZED_PCT:g}%",
        "normal": "otherwise",
    },
    "note": ("All fuel/workload/idle numbers are simple documented prototype "
             "assumptions for the demo — NOT real CAT operational formulas."),
}

_MODEL_INPUTS = ("task_type", "weather", "operator_skill", "machine_age")
_INPUT_LABELS = {"task_type": "Task type", "weather": "Weather",
                 "operator_skill": "Operator skill", "machine_age": "Machine age"}


def options() -> dict:
    """Valid input domains taken from the trained model's OneHotEncoder."""
    if not time_prediction.model_info():
        raise RuntimeError("Model not trained yet")
    cat = time_prediction._model.named_steps["pre"].named_transformers_["cat"]
    cats = {col: sorted(map(str, vals)) for col, vals in
            zip(time_prediction.CAT_COLS, cat.categories_)}
    return {"task_types": cats["task_type"], "weathers": cats["weather"],
            "skills": cats["operator_skill"],
            "machine_age": {"min": 1, "max": 15},
            "workload_pct": {"min": WORKLOAD_MIN, "max": WORKLOAD_MAX},
            "idle_pct": {"min": IDLE_MIN, "max": IDLE_MAX},
            "assumptions": ASSUMPTIONS}


def _outcome(workload_pct: float, idle_pct: float) -> dict:
    """Operating outcome/risk band (documented prototype heuristic)."""
    if workload_pct > OVERLOAD_PCT:
        return {"level": "HIGH", "label": "OVERLOAD RISK",
                "detail": f"Workload {workload_pct:g}% exceeds the "
                          f"{OVERLOAD_PCT:g}% prototype band — sustained "
                          "overloading risks component wear (simulated "
                          "heuristic, not a CAT limit)."}
    if idle_pct > HIGH_IDLE_PCT:
        return {"level": "MEDIUM", "label": "HIGH IDLE WASTE",
                "detail": f"Idling {idle_pct:g}% of the clock burns fuel "
                          "without productive work (simulated heuristic)."}
    if workload_pct < UNDERUTILIZED_PCT:
        return {"level": "MEDIUM", "label": "UNDERUTILIZED",
                "detail": f"Workload {workload_pct:g}% is below the "
                          f"{UNDERUTILIZED_PCT:g}% prototype band — machine "
                          "capacity is underused (simulated heuristic)."}
    return {"level": "LOW", "label": "NORMAL",
            "detail": "Workload and idle are inside the prototype normal "
                      "band (simulated heuristic)."}


def _scenario(inputs: dict) -> dict:
    """Full per-scenario result: model prediction + simulated layers."""
    pred = time_prediction.predict(inputs["task_type"], inputs["weather"],
                                   inputs["operator_skill"],
                                   inputs["machine_age"])
    model_min = pred["predicted_time_min"]                 # MODEL-PREDICTED
    w, i = inputs["workload_pct"], inputs["idle_pct"]
    productive_min = model_min * 100.0 / w                 # SIMULATED
    total_clock_min = productive_min / (1.0 - i / 100.0)   # SIMULATED
    idle_min = total_clock_min - productive_min
    fuel_l = (productive_min / 60.0) * PRODUCTIVE_BURN_L_H * (w / 100.0) \
        + (idle_min / 60.0) * IDLE_BURN_L_H                # SIMULATED
    return {
        "inputs": inputs,
        "model_predicted_min": model_min,                  # model-predicted
        "productive_min": round(productive_min, 1),        # simulated
        "idle_min": round(idle_min, 1),                    # simulated
        "total_clock_min": round(total_clock_min, 1),      # simulated
        "fuel_l": round(fuel_l, 1),                        # simulated
        "outcome": _outcome(w, i),                         # simulated heuristic
        "model_factors": pred["factors"],                  # model counterfactuals
    }

def _total(model_min: float, workload_pct: float, idle_pct: float) -> float:
    return (model_min * 100.0 / workload_pct) / (1.0 - idle_pct / 100.0)


def _model_only(inputs: dict) -> float:
    """Bare model prediction without the surrounding counterfactuals."""
    return float(time_prediction._model.predict(
        time_prediction.pd.DataFrame([{
            "task_type": inputs["task_type"], "weather": inputs["weather"],
            "operator_skill": inputs["operator_skill"],
            "machine_age": float(inputs["machine_age"])}]))[0])


def _top_factors(base_in: dict, scen_in: dict,
                 base_model_min: float, scen_model_min: float) -> list:
    """Decompose the total duration change into top contributing factors.

    Telescoping: model layer (at baseline simulated settings) -> workload ->
    idle, so contributions sum exactly to the total change. The model layer
    is attributed one input at a time (marginal effects; interactions
    between inputs are ignored — documented prototype limitation).
    """
    wb, ib = base_in["workload_pct"], base_in["idle_pct"]
    ws, is_ = scen_in["workload_pct"], scen_in["idle_pct"]

    factors = []

    # 1) Model layer, one input at a time (source = model-predicted).
    best_field, best_delta = None, 0.0
    for field in _MODEL_INPUTS:
        if scen_in[field] == base_in[field]:
            continue
        swapped = {**base_in, field: scen_in[field]}
        delta = _model_only(swapped) - base_model_min
        if abs(delta) > abs(best_delta):
            best_field, best_delta = field, delta
    model_layer = _total(scen_model_min, wb, ib) - _total(base_model_min, wb, ib)
    if best_field is not None:
        factors.append({
            "factor": f"{_INPUT_LABELS[best_field]}: "
                      f"{base_in[best_field]} → {scen_in[best_field]}",
            "impact_min": round(best_delta, 1),
            "source": "model",
            "detail": ("Largest single model-input change (one-at-a-time "
                       "marginal effect on the model prediction; "
                       "interactions ignored). Model layer total: "
                       f"{model_layer:+.1f} min.")})

    # 2) Workload change applied on top (source = simulated).
    if scen_in["workload_pct"] != base_in["workload_pct"]:
        wl_delta = _total(scen_model_min, ws, ib) - _total(scen_model_min, wb, ib)
        factors.append({
            "factor": f"Workload: {wb:g}% → {ws:g}%",
            "impact_min": round(wl_delta, 1), "source": "simulated",
            "detail": "Linear productivity assumption (simulated layer, "
                      "not a model feature)."})

    # 3) Idle change applied last (source = simulated).
    if scen_in["idle_pct"] != base_in["idle_pct"]:
        idle_delta = _total(scen_model_min, ws, is_) - _total(scen_model_min, ws, ib)
        factors.append({
            "factor": f"Idle time: {ib:g}% → {is_:g}%",
            "impact_min": round(idle_delta, 1), "source": "simulated",
            "detail": "Idle share stretches total clock time (simulated "
                      "layer, not a model feature)."})

    factors.sort(key=lambda f: abs(f["impact_min"]), reverse=True)
    return factors[:3]



def compare(baseline_in: dict, scenario_in: dict) -> dict:
    """Baseline vs what-if comparison with provenance labels."""
    base = _scenario(baseline_in)
    scen = _scenario(scenario_in)

    def _diff(b, s, unit):
        d = round(s - b, 1)
        pct = round(d / b * 100.0, 1) if b else None  # % only where meaningful
        return {"baseline": b, "scenario": s, "abs_diff": d,
                "pct_diff": pct, "unit": unit}

    _rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    comparison = {
        "duration": _diff(base["total_clock_min"], scen["total_clock_min"], "min"),
        "fuel": _diff(base["fuel_l"], scen["fuel_l"], "L"),
        "model_duration": _diff(base["model_predicted_min"],
                                scen["model_predicted_min"], "min"),
        "outcome_change": {
            "from": base["outcome"]["label"], "to": scen["outcome"]["label"],
            "from_level": base["outcome"]["level"],
            "to_level": scen["outcome"]["level"],
            "improved": _rank[scen["outcome"]["level"]]
                        < _rank[base["outcome"]["level"]]},
        "top_factors": _top_factors(baseline_in, scenario_in,
                                    base["model_predicted_min"],
                                    scen["model_predicted_min"]),
    }

    return {
        "baseline": base,
        "scenario": scen,
        "comparison": comparison,
        "provenance": {
            "model_predicted": ("Predicted duration comes from the SAME "
                                "trained task-time model used on the Task "
                                "Detail page (GradientBoosting on task type, "
                                "weather, skill, machine age)."),
            "simulated": ("Workload/idle duration effects, fuel usage and "
                          "the outcome bands are a SIMULATED prototype layer "
                          "with documented assumptions — NOT real CAT "
                          "formulas."),
            "assumptions": ASSUMPTIONS,
        },
        "model": time_prediction.model_info(),
    }

