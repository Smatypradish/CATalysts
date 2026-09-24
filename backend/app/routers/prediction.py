from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import time_prediction, what_if

router = APIRouter(prefix="/api/prediction", tags=["prediction"])


class PredictRequest(BaseModel):
    task_type: str
    weather: str
    operator_skill: str
    machine_age: float


@router.get("/model-info")
def model_info():
    return time_prediction.model_info()


@router.post("/predict")
def predict(req: PredictRequest):
    return time_prediction.predict(req.task_type, req.weather,
                                   req.operator_skill, req.machine_age)


@router.get("/history/{task_type}")
def history(task_type: str, db: Session = Depends(get_db)):
    return time_prediction.compare_to_history(db, task_type)


class ScenarioInputs(BaseModel):
    # Model features (same pipeline as task-time prediction) ...
    task_type: str
    weather: str
    operator_skill: str
    machine_age: float = Field(ge=1, le=20)
    # ... plus SIMULATED prototype inputs (not model features)
    workload_pct: float = Field(ge=what_if.WORKLOAD_MIN, le=what_if.WORKLOAD_MAX)
    idle_pct: float = Field(ge=what_if.IDLE_MIN, le=what_if.IDLE_MAX)


class WhatIfRequest(BaseModel):
    baseline: ScenarioInputs
    scenario: ScenarioInputs


@router.get("/what-if/options")
def what_if_options():
    """Input domains for the What-If Simulator (from the trained encoder)."""
    return what_if.options()


@router.post("/what-if")
def what_if_compare(req: WhatIfRequest):
    """Baseline vs what-if: model duration + simulated fuel/outcome layers."""
    return what_if.compare(req.baseline.model_dump(), req.scenario.model_dump())
