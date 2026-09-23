from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Machine, Operator, ScheduledTask
from ..services import (behavior_analysis, safety_rules, simulator,
                        time_prediction, training_recommender)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/{operator_id}")
def dashboard(operator_id: str, db: Session = Depends(get_db)):
    op = db.query(Operator).filter(Operator.operator_id == operator_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")

    tasks = (db.query(ScheduledTask)
             .filter(ScheduledTask.operator_id == operator_id)
             .order_by(ScheduledTask.id).all())
    today = [{
        "task_code": t.task_code, "task_type": t.task_type, "machine_id": t.machine_id,
        "weather": t.weather, "site": t.site, "status": t.status,
        "estimated_time": t.estimated_time, "predicted_time": t.predicted_time,
        "actual_time": t.actual_time,
    } for t in tasks]

    active = simulator.active_task(db, operator_id)
    machine = None
    if active:
        machine = db.query(Machine).filter(Machine.machine_id == active.machine_id).first()
    elif tasks:
        machine = db.query(Machine).filter(Machine.machine_id == tasks[0].machine_id).first()

    safety = safety_rules.safety_summary(db, operator_id)
    behavior = behavior_analysis.analyze(db, operator_id)
    recs = training_recommender.recommend_from_findings(db, operator_id,
                                                        behavior["findings"])

    # AI-generated insights (deterministic summaries over live data).
    insights = []
    n_crit = sum(1 for f in behavior["findings"] if f["severity"] in ("CRITICAL", "HIGH"))
    if n_crit:
        insights.append(f"{n_crit} high/critical behavior finding(s) on record - review "
                        f"the Behavior page and complete the recommended training.")
    pending = [t for t in tasks if t.status == "Scheduled"]
    if pending:
        t0 = pending[0]
        m = db.query(Machine).filter(Machine.machine_id == t0.machine_id).first()
        try:
            p = time_prediction.predict(t0.task_type, t0.weather, op.skill,
                                        m.age_years if m else 3.0)
            delta = p["predicted_time_min"] - t0.estimated_time
            if delta > 3:
                causes = []
                if t0.weather != "Sunny":
                    causes.append(f"{t0.weather} weather")
                if op.skill != "Expert":
                    causes.append(f"{op.skill} skill level")
                reason = (" mainly due to " + " and ".join(causes)) if causes else ""
                insights.append(f"Next task {t0.task_code} ({t0.task_type}) is likely to "
                                f"take ~{p['predicted_time_min']:.0f} min, about "
                                f"{delta:.0f} min longer than the planner estimate{reason}.")
            else:
                insights.append(f"Next task {t0.task_code} ({t0.task_type}) looks on plan "
                                f"at ~{p['predicted_time_min']:.0f} min.")
        except RuntimeError:
            pass
    if safety["status"] != "SAFE":
        insights.append(f"Safety status is {safety['status']}: {safety['open_incidents']} "
                        f"open incident(s) need acknowledgement.")
    if not insights:
        insights.append("All clear: no pressing safety, behavior or scheduling issues.")

    return {
        "date": date.today().isoformat(),
        "operator": {"operator_id": op.operator_id, "name": op.name,
                     "skill": op.skill, "certifications": op.certifications},
        "machine": ({"machine_id": machine.machine_id, "model": machine.model,
                     "machine_type": machine.machine_type, "age_years": machine.age_years,
                     "engine_hours": machine.engine_hours, "status": machine.status}
                    if machine else None),
        "tasks": today,
        "active_task": active.task_code if active else None,
        "live_session": bool(simulator.get_live(operator_id)),
        "safety": safety,
        "behavior_counts": {
            "findings": len(behavior["findings"]),
            "critical_high": n_crit,
        },
        "training_recommendations": recs[:3],
        "insights": insights,
        "model_info": time_prediction.model_info(),
    }
