from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    operator_id: str
    message: str


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    return assistant.answer(db, req.operator_id, req.message)
