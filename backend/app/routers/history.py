from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident, ScheduledTask, TaskHistory
from ..services import behavior_analysis

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/{operator_id}/performance")
def performance(operator_id: str, db: Session = Depends(get_db)):
    """Incident/performance history: predicted vs actual + safety/behavior summary."""
    completed = (db.query(ScheduledTask)
                 .filter(ScheduledTask.operator_id == operator_id,
                         ScheduledTask.status == "Completed")
                 .order_by(ScheduledTask.completed_at.desc()).all())
    completed_rows = [{
        "task_code": t.task_code, "task_type": t.task_type, "weather": t.weather,
        "estimated_time": t.estimated_time, "predicted_time": t.predicted_time,
        "actual_time": t.actual_time,
        "variance_min": (round(t.actual_time - t.predicted_time, 1)
                         if t.actual_time is not None and t.predicted_time is not None
                         else None),
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    } for t in completed]

    past = (db.query(TaskHistory).order_by(TaskHistory.id).all())
    past_rows = [{
        "task_id": r.task_id, "task_type": r.task_type, "weather": r.weather,
        "operator_skill": r.operator_skill, "machine_age": r.machine_age,
        "estimated_time": r.estimated_time, "actual_time": r.actual_time,
        "source": r.source,
    } for r in past]

    incidents = (db.query(Incident).filter(Incident.operator_id == operator_id)
                 .order_by(Incident.timestamp.desc()).all())
    behavior = behavior_analysis.analyze(db, operator_id)

    return {
        "completed_tasks": completed_rows,
        "historical_records": past_rows,
        "incident_count": len(incidents),
        "incidents_by_severity": {
            s: sum(1 for i in incidents if i.severity == s)
            for s in ("CRITICAL", "WARNING", "INFO")},
        "behavior_baseline": behavior.get("baseline", {}),
        "open_findings": len(behavior.get("findings", [])),
    }
