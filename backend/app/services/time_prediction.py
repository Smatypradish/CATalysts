"""Task time estimation pipeline (scikit-learn).

Trained on the 100 task-history records seeded from data/task_records_100.csv:
the 5 real Caterpillar-supplied rows (source='dataset') PLUS 95 clearly-labelled
synthetic rows (source='synthetic') — a 5-row supplied dataset cannot train a
regressor on its own, so labelled synthetic augmentation is required and documented
(backend/generate_task_records_100.py).

Input features, BY DESIGN: task_type, weather, operator_skill (one-hot) and
machine_age (numeric). Estimated Time is NEVER used as an input feature: it is a
planner guess, not a physical driver of duration, and using it would leak the
very thing we are trying to improve on into the model.

Honest evaluation — no accuracy percentages are reported anywhere:
  1. The 95 synthetic rows are split 80/20 (seeded) into train/validation; the
     holdout MAE/RMSE measures fit to the synthetic distribution only.
  2. Separately, leave-one-out MAE over the 5 REAL rows shows how predictions
     behave on the supplied data. This is a very small prototype evaluation,
     explicitly NOT production accuracy.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
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
    X = df[CAT_COLS + NUM_COLS]   # estimated_time deliberately excluded
    y = df["actual_time"]
    _model = _build_pipeline().fit(X, y)

    synth = df[df.source == "synthetic"]
    real = df[df.source == "dataset"]

    # --- Validation 1: seeded 80/20 train/validation split of the 95 SYNTHETIC
    # rows. The holdout MAE/RMSE only measures fit to the synthetic
    # distribution — it says nothing about real-world accuracy on its own.
    s_train, s_val = train_test_split(synth, test_size=0.2, random_state=42)
    vm = _build_pipeline().fit(s_train[CAT_COLS + NUM_COLS], s_train["actual_time"])
    vp = vm.predict(s_val[CAT_COLS + NUM_COLS])
    val_mae = round(float(mean_absolute_error(s_val["actual_time"], vp)), 1)
    val_rmse = round(float(np.sqrt(mean_squared_error(s_val["actual_time"], vp))), 1)

    # --- Validation 2: leave-one-out over the 5 REAL dataset rows (each fold
    # trains on the other 99 records). Reported as a very small prototype
    # evaluation of how predictions behave on the supplied rows — nothing more.
    errs = []
    for i in real.index:
        train_idx = df.index.difference([i])
        m = _build_pipeline().fit(X.loc[train_idx], y.loc[train_idx])
        pred = float(m.predict(X.loc[[i]])[0])
        errs.append(abs(pred - y.loc[i]))
    loo_mae = round(float(np.mean(errs)), 1) if errs else None

    _meta = {
        "n_total": len(df),
        "n_real_dataset": int(len(real)),
        "n_synthetic": int(len(synth)),
        "n_synth_train": int(len(s_train)),
        "n_synth_validation": int(len(s_val)),
        "synth_validation_mae_min": val_mae,
        "synth_validation_rmse_min": val_rmse,
        "loo_mae_real_rows_min": loo_mae,
        "features": CAT_COLS + NUM_COLS,
        "excluded_features": ["estimated_time"],
        "algorithm": "GradientBoostingRegressor + OneHotEncoder(task_type, weather, skill)",
        "evaluation_note": (
            f"Synthetic holdout: {val_mae} min MAE / {val_rmse} min RMSE on "
            f"{len(s_val)} held-out synthetic rows (80/20 split of the 95). "
            f"Real-data check: {loo_mae} min leave-one-out MAE over the 5 "
            "supplied Caterpillar rows — a very small prototype evaluation, "
            "not a measure of production accuracy."),
        "disclaimer": (
            "Prototype model trained on 5 supplied Caterpillar task records plus "
            "95 clearly-labelled synthetic records. Estimated Time is not a model "
            "input. The 5-row leave-one-out MAE is a very small prototype "
            "evaluation only — real deployment requires real CAT fleet historical "
            "data; do not treat any reported MAE as production accuracy."),
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
