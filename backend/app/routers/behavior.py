from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import behavior_analysis, training_recommender

router = APIRouter(prefix="/api/behavior", tags=["behavior"])


class SimulatePattern(BaseModel):
    pattern: str  # excessive_idling | low_load | fuel_anomaly


@router.get("/{operator_id}/analyze")
def analyze(operator_id: str, db: Session = Depends(get_db)):
    result = behavior_analysis.analyze(db, operator_id)
    result["training_recommendations"] = training_recommender.recommend_from_findings(
        db, operator_id, result["findings"])
    return result


@router.get("/{operator_id}/telemetry")
def telemetry(operator_id: str, db: Session = Depends(get_db)):
    from ..models import Telemetry
    rows = (db.query(Telemetry).filter(Telemetry.operator_id == operator_id)
            .order_by(Telemetry.timestamp).all())
    return [{"timestamp": r.timestamp.isoformat(), "machine_id": r.machine_id,
             "engine_hours": r.engine_hours, "fuel_used": r.fuel_used,
             "load_cycles": r.load_cycles, "idling_time": r.idling_time,
             "seatbelt_status": r.seatbelt_status,
             "safety_alert_triggered": r.safety_alert_triggered,
             "source": r.source} for r in rows]
