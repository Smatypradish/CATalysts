"""Map detected behaviors -> training modules and manage assignments."""
from datetime import datetime

from ..models import TrainingAssignment, TrainingModule

# finding code -> module code
FINDING_TO_MODULE = {
    "EXCESSIVE_IDLING": "TM-IDLE",
    "LOW_LOAD": "TM-IDLE",
    "FUEL_ANOMALY": "TM-FUEL",
    "SAFETY_VIOLATION": "TM-SEATBELT",
    "REPEAT_VIOLATIONS": "TM-SEATBELT",
    "PROXIMITY": "TM-PROX",
}


def recommend_from_findings(db, operator_id: str, findings: list) -> list:
    """Build deduplicated, behaviour-linked training recommendations."""
    recs, seen = [], set()
    for f in findings:
        code = f.get("recommended_module") or FINDING_TO_MODULE.get(f["code"])
        if not code or code in seen:
            continue
        seen.add(code)
        module = db.query(TrainingModule).filter(TrainingModule.code == code).first()
        if module:
            recs.append({
                "module_code": module.code, "title": module.title,
                "format": module.format, "duration_min": module.duration_min,
                "category": module.category,
                "reason": f"Recommended because '{f['title']}' was detected: {f['detected']}",
                "triggered_by": f["code"], "severity": f["severity"],
            })
    return recs


def assign(db, operator_id: str, module_code: str, reason: str) -> TrainingAssignment:
    existing = (db.query(TrainingAssignment)
                .filter(TrainingAssignment.operator_id == operator_id,
                        TrainingAssignment.module_code == module_code,
                        TrainingAssignment.status == "Assigned").first())
    if existing:
        return existing
    a = TrainingAssignment(operator_id=operator_id, module_code=module_code,
                           reason=reason, status="Assigned",
                           assigned_at=datetime.utcnow())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a
