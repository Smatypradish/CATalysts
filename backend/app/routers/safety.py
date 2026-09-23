from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import safety_rules, simulator

router = APIRouter(prefix="/api/safety", tags=["safety"])


class SimulateRequest(BaseModel):
    operator_id: str
    event_type: str  # seatbelt_violation | seatbelt_fixed | proximity_hazard |
                     # person_approaching | proximity_clear | weather_change |
                     # excessive_idling | low_load | fuel_anomaly
    weather: str | None = None  # for weather_change: Sunny|Cloudy|Rainy|Windy|Fog|Night


@router.get("/live/{operator_id}")
def live(operator_id: str, db: Session = Depends(get_db)):
    """Advance and return simulated live telemetry (polled by the UI)."""
    snap = simulator.tick(db, operator_id)
    if not snap:
        return {"active": False, "message": "No active operation session."}
    return {"active": True, **snap}


@router.post("/simulate")
def simulate(req: SimulateRequest, db: Session = Depends(get_db)):
    result = simulator.simulate_event(db, req.operator_id, req.event_type,
                                      req.weather)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/status/{operator_id}")
def status(operator_id: str, db: Session = Depends(get_db)):
    return safety_rules.safety_summary(db, operator_id)
