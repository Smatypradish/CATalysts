"""AI assistant: intent-based retrieval over live application data.

Deliberately NOT a generic chatbot: it answers machine/operator questions
using the app's own data (tasks, predictions, behavior findings, incidents,
training) and returns explanations/recommendations. Safety-critical answers
come from the deterministic rule engine, never from free-form generation.
Extension point: an LLM could rephrase these grounded answers later.
"""
from ..models import Incident, Machine, Operator, ScheduledTask, TrainingModule
from . import behavior_analysis, safety_rules, simulator, time_prediction
from . import training_recommender


def answer(db, operator_id: str, message: str) -> dict:
    msg = (message or "").lower()
    op = db.query(Operator).filter(Operator.operator_id == operator_id).first()

    if any(k in msg for k in ("task", "schedule", "today", "job")):
        tasks = db.query(ScheduledTask).filter(
            ScheduledTask.operator_id == operator_id).all()
        if not tasks:
            return _resp("No tasks scheduled today.", ["scheduled_tasks"])
        lines = [f"- {t.task_code}: {t.task_type} at {t.site} ({t.status}), "
                 f"est. {t.estimated_time:.0f} min"
                 + (f", predicted {t.predicted_time:.0f} min" if t.predicted_time else "")
                 for t in tasks]
        return _resp(f"You have {len(tasks)} task(s) scheduled today:\n" + "\n".join(lines),
                     ["scheduled_tasks"])

    if any(k in msg for k in ("safe", "seatbelt", "belt", "proximity", "hazard", "alert")):
        summary = safety_rules.safety_summary(db, operator_id)
        live = simulator.get_live(operator_id)
        parts = [f"Current safety status: {summary['status']} "
                 f"({summary['open_incidents']} open incident(s), "
                 f"{summary['critical_incidents']} critical)."]
        if live:
            parts.append(f"Live (simulated) sensors: seatbelt {live['seatbelt']}, "
                         f"proximity {live['proximity_m']} m.")
        if summary["latest"]:
            parts.append("Latest open events:\n" + "\n".join(
                f"- [{i['severity']}] {i['type']}: {i['description']}"
                for i in summary["latest"]))
        parts.append("Reminder: seatbelt must be fastened whenever the engine is running; "
                     "keep the proximity zone clear. These rules are enforced "
                     "deterministically, not by me.")
        return _resp("\n".join(parts), ["safety_rules", "incidents", "simulator"])

    if any(k in msg for k in ("behavior", "behaviour", "unusual", "anomal",
                              "idle", "idling", "fuel")):
        res = behavior_analysis.analyze(db, operator_id)
        if not res["findings"]:
            return _resp("No unusual behavior detected in your telemetry. Keep it up!",
                         ["behavior_analysis"])
        top = res["findings"][:4]
        lines = [f"- [{f['severity']}] {f['title']}: {f['detected']}\n  Why: {f['why']}\n"
                 f"  Action: {f['action']}" for f in top]
        return _resp(f"I analysed {res['records']} telemetry records "
                     f"({res['baseline'].get('dataset_records', 0)} from the supplied "
                     f"dataset). Findings:\n" + "\n".join(lines),
                     ["behavior_analysis", "telemetry"])
    return _answer2(db, operator_id, msg, op)


def _resp(text, sources):
    return {"answer": text, "sources": sources,
            "note": "Grounded in live application data; safety-critical logic is deterministic."}


def _answer2(db, operator_id, msg, op) -> dict:
    if any(k in msg for k in ("predict", "estimate", "how long", "time")):
        task = (db.query(ScheduledTask)
                .filter(ScheduledTask.operator_id == operator_id,
                        ScheduledTask.status.in_(["Scheduled", "In Progress"]))
                .order_by(ScheduledTask.id).first())
        if not task:
            return _resp("No pending task to estimate.", ["time_prediction"])
        machine = db.query(Machine).filter(Machine.machine_id == task.machine_id).first()
        pred = time_prediction.predict(task.task_type, task.weather,
                                       (op.skill if op else "Intermediate"),
                                       machine.age_years if machine else 3)
        factors = "\n".join(f"- {f['factor']}: {f['detail']}" for f in pred["factors"])
        return _resp(f"For {task.task_code} ({task.task_type}, {task.weather} weather, "
                     f"{op.skill if op else '?'} skill, machine age "
                     f"{machine.age_years if machine else '?'} yrs) I predict about "
                     f"{pred['predicted_time_min']:.0f} min (planner estimate: "
                     f"{task.estimated_time:.0f} min).\nFactors:\n{factors}\n"
                     f"Note: {pred['model'].get('disclaimer', '')}",
                     ["time_prediction"])

    if any(k in msg for k in ("train", "learn", "course", "module", "recommend")):
        res = behavior_analysis.analyze(db, operator_id)
        recs = training_recommender.recommend_from_findings(db, operator_id, res["findings"])
        if not recs:
            mods = db.query(TrainingModule).limit(3).all()
            return _resp("No behaviour-linked gaps right now. Popular modules:\n" +
                         "\n".join(f"- {m.title} ({m.format}, {m.duration_min} min)"
                                   for m in mods), ["training"])
        return _resp("Based on your detected behavior I recommend:\n" +
                     "\n".join(f"- {r['title']} ({r['format']}, {r['duration_min']} min)\n"
                               f"  Reason: {r['reason']}" for r in recs),
                     ["training_recommender", "behavior_analysis"])

    if any(k in msg for k in ("incident", "history", "log", "report")):
        incs = (db.query(Incident).filter(Incident.operator_id == operator_id)
                .order_by(Incident.timestamp.desc()).limit(5).all())
        if not incs:
            return _resp("No incidents logged for you. Great safety record!", ["incidents"])
        return _resp("Recent incidents:\n" + "\n".join(
            f"- {i.timestamp:%Y-%m-%d %H:%M} [{i.severity}] {i.incident_type} on "
            f"{i.machine_id} - {i.status}" for i in incs), ["incidents"])

    if any(k in msg for k in ("machine", "exc", "engine", "status")):
        machines = db.query(Machine).all()
        return _resp("Fleet status:\n" + "\n".join(
            f"- {m.machine_id} ({m.model}, {m.machine_type}): {m.status}, "
            f"{m.engine_hours} engine hrs, age {m.age_years} yrs" for m in machines),
            ["machines"])

    return _resp("I am your Operator Companion. I can answer about: today's tasks, "
                 "safety status and alerts, unusual behavior findings, task-time "
                 "predictions, training recommendations, incidents and machine status. "
                 "Try: 'What are my tasks today?' or 'Why was my behavior flagged?'",
                 ["help"])
