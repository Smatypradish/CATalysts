from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TrainingAssignment, TrainingModule
from ..services import behavior_analysis, training_recommender

router = APIRouter(prefix="/api/training", tags=["training"])


class AssignRequest(BaseModel):
    operator_id: str
    module_code: str
    reason: str = "Manual assignment"


class InstructorBooking(BaseModel):
    operator_id: str
    module_code: str
    preferred_slot: str


def _module(m: TrainingModule) -> dict:
    return {"code": m.code, "title": m.title, "category": m.category,
            "format": m.format, "duration_min": m.duration_min,
            "description": m.description}


def _assignment(a: TrainingAssignment, db: Session) -> dict:
    m = db.query(TrainingModule).filter(TrainingModule.code == a.module_code).first()
    return {"id": a.id, "operator_id": a.operator_id, "module_code": a.module_code,
            "module_title": m.title if m else a.module_code,
            "format": m.format if m else None,
            "reason": a.reason, "status": a.status,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None}


@router.get("/modules")
def modules(db: Session = Depends(get_db)):
    return [_module(m) for m in db.query(TrainingModule).all()]


@router.get("/recommendations/{operator_id}")
def recommendations(operator_id: str, db: Session = Depends(get_db)):
    """Recommendations derived from detected behavior (not hardcoded)."""
    res = behavior_analysis.analyze(db, operator_id)
    return training_recommender.recommend_from_findings(db, operator_id, res["findings"])


@router.get("/assignments/{operator_id}")
def assignments(operator_id: str, db: Session = Depends(get_db)):
    rows = (db.query(TrainingAssignment)
            .filter(TrainingAssignment.operator_id == operator_id)
            .order_by(TrainingAssignment.assigned_at.desc()).all())
    return [_assignment(a, db) for a in rows]


@router.post("/assign")
def assign(req: AssignRequest, db: Session = Depends(get_db)):
    if not db.query(TrainingModule).filter(TrainingModule.code == req.module_code).first():
        raise HTTPException(status_code=404, detail="Module not found")
    a = training_recommender.assign(db, req.operator_id, req.module_code, req.reason)
    return _assignment(a, db)


@router.post("/assignments/{assignment_id}/complete")
def complete(assignment_id: int, db: Session = Depends(get_db)):
    a = db.query(TrainingAssignment).filter(TrainingAssignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    a.status = "Completed"
    a.completed_at = datetime.utcnow()
    db.commit()
    return _assignment(a, db)


@router.post("/book-instructor")
def book_instructor(req: InstructorBooking, db: Session = Depends(get_db)):
    m = db.query(TrainingModule).filter(TrainingModule.code == req.module_code).first()
    if not m:
        raise HTTPException(status_code=404, detail="Module not found")
    a = training_recommender.assign(
        db, req.operator_id, req.module_code,
        f"Instructor-led session booked for {req.preferred_slot} (simulated booking).")
    return {"booking_confirmed": True, "slot": req.preferred_slot,
            "module": _module(m), "assignment": _assignment(a, db),
            "note": "Booking is simulated for the prototype; no real calendar integration."}
