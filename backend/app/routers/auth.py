from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Operator

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    operator_id: str
    pin: str


def _profile(op: Operator) -> dict:
    return {"operator_id": op.operator_id, "name": op.name, "skill": op.skill,
            "certifications": op.certifications}


@router.get("/operators")
def list_operators(db: Session = Depends(get_db)):
    """Login screen helper: demo operator directory."""
    return [{"operator_id": o.operator_id, "name": o.name, "skill": o.skill}
            for o in db.query(Operator).all()]


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    op = db.query(Operator).filter(Operator.operator_id == req.operator_id).first()
    if not op or op.pin != req.pin:
        raise HTTPException(status_code=401, detail="Invalid operator ID or PIN")
    return _profile(op)
