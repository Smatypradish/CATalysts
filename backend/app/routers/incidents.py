from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

Severity = Literal["INFO", "WARNING", "HIGH", "CRITICAL"]
IncidentStatus = Literal["Open", "Acknowledged", "Resolved"]


class IncidentCreate(BaseModel):
    operator_id: str
    machine_id: str
    incident_type: str
    severity: Severity = "INFO"
    description: str
    task_code: str | None = None


class IncidentUpdate(BaseModel):
    status: IncidentStatus | None = None
    action_taken: str | None = None


def _row(i: Incident) -> dict:
    return {"id": i.id,
            "timestamp": i.timestamp.isoformat() if i.timestamp else None,
            "operator_id": i.operator_id, "machine_id": i.machine_id,
            "task_code": i.task_code, "incident_type": i.incident_type,
            "severity": i.severity, "description": i.description,
            "status": i.status, "action_taken": i.action_taken, "source": i.source}


@router.get("")
def list_incidents(operator_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Incident)
    if operator_id:
        q = q.filter(Incident.operator_id == operator_id)
    return [_row(i) for i in q.order_by(Incident.timestamp.desc()).all()]


@router.post("")
def create_incident(req: IncidentCreate, db: Session = Depends(get_db)):
    inc = Incident(timestamp=datetime.utcnow(), operator_id=req.operator_id,
                   machine_id=req.machine_id, task_code=req.task_code,
                   incident_type=req.incident_type, severity=req.severity,
                   description=req.description, status="Open",
                   action_taken="", source="manual")
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return _row(inc)


@router.patch("/{incident_id}")
def update_incident(incident_id: int, req: IncidentUpdate, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if req.status:
        inc.status = req.status
    if req.action_taken is not None:
        inc.action_taken = req.action_taken
    db.commit()
    db.refresh(inc)
    return _row(inc)
