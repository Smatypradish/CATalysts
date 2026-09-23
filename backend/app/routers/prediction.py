from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import time_prediction

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
