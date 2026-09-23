"""Task time estimation pipeline (scikit-learn).

Trained on the 5 real rows from Dataset 2 PLUS clearly-labelled synthetic rows
(small supplied dataset -> synthetic augmentation is required and documented).
Honesty: leave-one-out MAE on the real rows is reported in every response.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ..models import TaskHistory

CAT_COLS = ["task_type", "weather", "operator_skill"]
NUM_COLS = ["machine_age"]

_model = None
_meta: dict = {}


def _frame(rows):
    return pd.DataFrame([{
        "task_type": r.task_type, "weather": r.weather,
        "operator_skill": r.operator_skill, "machine_age": float(r.machine_age),
        "actual_time": float(r.actual_time), "estimated_time": float(r.estimated_time),
        "source": r.source,
    } for r in rows])


def _build_pipeline():
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ("num", "passthrough", NUM_COLS),
    ])
    return Pipeline([("pre", pre),
                     ("reg", GradientBoostingRegressor(random_state=42))])


def train(db) -> dict:
    global _model, _meta
    rows = db.query(TaskHistory).all()
    df = _frame(rows)
    X = df[CAT_COLS + NUM_COLS]
    y = df["actual_time"]
    _model = _build_pipeline().fit(X, y)

    # Honest evaluation: leave-one-out on the 5 REAL dataset rows only.
    real = df[df.source == "dataset"]
    errs = []
    for i in real.index:
        train_idx = df.index.difference([i])
        m = _build_pipeline().fit(X.loc[train_idx], y.loc[train_idx])
        pred = float(m.predict(X.loc[[i]])[0])
        errs.append(abs(pred - y.loc[i]))
    loo_mae = round(float(np.mean(errs)), 1) if errs else None

    _meta = {
        "n_total": len(df),
        "n_real_dataset": int((df.source == "dataset").sum()),
        "n_synthetic": int((df.source == "synthetic").sum()),
        "loo_mae_real_rows_min": loo_mae,
        "algorithm": "GradientBoostingRegressor + OneHotEncoder(task_type, weather, skill)",
        "disclaimer": ("Prototype model: supplied dataset has only 5 rows, so it was "
                       "augmented with clearly-labelled synthetic rows. Real deployment "
                       "requires real CAT fleet historical data; do not treat the MAE as "
                       "production accuracy."),
    }
    return _meta


def model_info() -> dict:
    return _meta


def predict(task_type: str, weather: str, operator_skill: str,
            machine_age: float) -> dict:
    """Predict completion time + counterfactual factor explanation."""
    if _model is None:
        raise RuntimeError("Model not trained yet")

    def _p(tt, w, s, a):
        X = pd.DataFrame([{"task_type": tt, "weather": w, "operator_skill": s,
                           "machine_age": float(a)}])
        return float(_model.predict(X)[0])

    pred = _p(task_type, weather, operator_skill, machine_age)

    # Counterfactual baseline: ideal conditions (Sunny, Expert, 1-year machine).
    base = _p(task_type, "Sunny", "Expert", 1)
    weather_delta = _p(task_type, weather, "Expert", 1) - base
    skill_delta = _p(task_type, "Sunny", operator_skill, 1) - base
    age_delta = _p(task_type, "Sunny", "Expert", machine_age) - base

    factors = []
    if weather_delta > 1:
        factors.append({"factor": f"Weather: {weather}",
                        "impact_min": round(weather_delta, 1),
                        "detail": f"Adverse weather adds ~{weather_delta:.0f} min vs sunny "
                                  f"conditions (traction, visibility, cycle slowdown)."})
    if skill_delta > 1:
        factors.append({"factor": f"Operator skill: {operator_skill}",
                        "impact_min": round(skill_delta, 1),
                        "detail": f"Non-expert operation historically adds ~{skill_delta:.0f} min "
                                  f"(slower cycles, more corrections)."})
    if age_delta > 1:
        factors.append({"factor": f"Machine age: {machine_age:g} yrs",
                        "impact_min": round(age_delta, 1),
                        "detail": f"Older machine adds ~{age_delta:.0f} min (hydraulic wear, "
                                  f"lower efficiency)."})
    if not factors:
        factors.append({"factor": "Conditions near ideal", "impact_min": 0.0,
                        "detail": "Weather, skill and machine age are all close to the "
                                  "best historical conditions for this task type."})

    return {
        "predicted_time_min": round(pred, 1),
        "ideal_conditions_min": round(base, 1),
        "factors": factors,
        "model": _meta,
    }


def compare_to_history(db, task_type: str) -> dict:
    """Historical context for a task type (used on the task detail page)."""
    rows = db.query(TaskHistory).filter(TaskHistory.task_type == task_type).all()
    if not rows:
        return {"samples": 0}
    actuals = [r.actual_time for r in rows]
    ests = [r.estimated_time for r in rows]
    return {
        "samples": len(rows),
        "avg_actual_min": round(float(np.mean(actuals)), 1),
        "avg_estimated_min": round(float(np.mean(ests)), 1),
        "min_actual": min(actuals), "max_actual": max(actuals),
    }
