from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Machine, Operator, ScheduledTask
from ..services import simulator, time_prediction

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CompleteRequest(BaseModel):
    # Optional manual override; must be a plausible task duration in minutes
    # (positive, capped at one 8-hour shift). Omit to use the demo simulation.
    actual_time: float | None = Field(default=None, gt=0, le=480)


def _row(t: ScheduledTask) -> dict:
    return {"task_code": t.task_code, "operator_id": t.operator_id,
            "machine_id": t.machine_id, "task_type": t.task_type,
            "weather": t.weather, "site": t.site,
            "scheduled_date": t.scheduled_date, "shift_start": t.shift_start,
            "status": t.status, "estimated_time": t.estimated_time,
            "predicted_time": t.predicted_time, "actual_time": t.actual_time,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None}


@router.get("/today/{operator_id}")
def todays_tasks(operator_id: str, db: Session = Depends(get_db)):
    tasks = (db.query(ScheduledTask)
             .filter(ScheduledTask.operator_id == operator_id)
             .order_by(ScheduledTask.id).all())
    return {"date": date.today().isoformat(), "tasks": [_row(t) for t in tasks]}


@router.get("/{task_code}")
def task_detail(task_code: str, db: Session = Depends(get_db)):
    t = db.query(ScheduledTask).filter(ScheduledTask.task_code == task_code).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    machine = db.query(Machine).filter(Machine.machine_id == t.machine_id).first()
    op = db.query(Operator).filter(Operator.operator_id == t.operator_id).first()
    return {**_row(t),
            "machine": {"machine_id": machine.machine_id, "model": machine.model,
                        "age_years": machine.age_years,
                        "engine_hours": machine.engine_hours,
                        "status": machine.status} if machine else None,
            "operator_skill": op.skill if op else None,
            "history": time_prediction.compare_to_history(db, t.task_type)}


@router.post("/{task_code}/predict")
def predict_task(task_code: str, db: Session = Depends(get_db)):
    """Predict completion time for a scheduled task and persist it."""
    t = db.query(ScheduledTask).filter(ScheduledTask.task_code == task_code).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    machine = db.query(Machine).filter(Machine.machine_id == t.machine_id).first()
    op = db.query(Operator).filter(Operator.operator_id == t.operator_id).first()
    result = time_prediction.predict(t.task_type, t.weather,
                                     op.skill if op else "Intermediate",
                                     machine.age_years if machine else 3.0)
    t.predicted_time = result["predicted_time_min"]
    db.commit()
    return result


@router.post("/{task_code}/start")
def start_task(task_code: str, db: Session = Depends(get_db)):
    t = db.query(ScheduledTask).filter(ScheduledTask.task_code == task_code).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if simulator.active_task(db, t.operator_id):
        raise HTTPException(status_code=409,
                            detail="Another task is already in progress")
    t.status = "In Progress"
    t.started_at = datetime.utcnow()
    db.commit()
    live = simulator.start_session(t.operator_id, t.machine_id, t.task_code, t.weather)
    return {"task": _row(t), "live": live}


@router.post("/{task_code}/complete")
def complete_task(task_code: str, req: CompleteRequest, db: Session = Depends(get_db)):
    t = db.query(ScheduledTask).filter(ScheduledTask.task_code == task_code).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    session = simulator.end_session(db, t.operator_id)
    # Demo acceleration: scale a short demo run up to a realistic duration near prediction.
    base = t.predicted_time or t.estimated_time
    import random
    rng = random.Random()
    actual = req.actual_time or round(base * rng.uniform(0.92, 1.18), 1)
    t.actual_time = actual
    t.status = "Completed"
    t.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return {"task": _row(t), "session": session,
            "variance_min": round(actual - (t.predicted_time or t.estimated_time), 1),
            "note": "Actual time is simulated for the demo (scaled around the prediction)."}
