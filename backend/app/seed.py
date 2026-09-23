"""Seed the SQLite database.

Sources of truth:
  data/machine_telemetry.csv  -> Dataset 1 (loaded verbatim, source='dataset')
  data/task_records.csv       -> Dataset 2 (loaded verbatim, source='dataset')

Everything else is clearly labelled demo/synthetic data:
  telemetry  rows added for baseline statistics    -> source='simulated'
  task_history rows for the ML pipeline            -> source='synthetic'
"""
import random
from datetime import date, datetime, timedelta

import pandas as pd

from .database import DATA_DIR, Base, SessionLocal, engine
from .models import (Machine, Operator, ScheduledTask, TaskHistory, Telemetry,
                     TrainingModule)

# Documented generation formula for synthetic task-history rows.
BASE_MINUTES = {"Earth Excavation": 55, "Trenching": 50, "Material Loading": 35,
                "Grading": 40, "Demolition": 85}
WEATHER_FACTOR = {"Sunny": 1.00, "Cloudy": 1.08, "Rainy": 1.22, "Windy": 1.15}
SKILL_FACTOR = {"Expert": 0.92, "Intermediate": 1.05, "Beginner": 1.22}


def reset_and_seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    rng = random.Random(42)

    # ---- Operators / machines (demo master data) ----
    db.add_all([
        Operator(operator_id="OP1001", name="Arun Kumar", skill="Intermediate",
                 pin="1001", certifications="Excavator L2"),
        Operator(operator_id="OP1002", name="Priya Sharma", skill="Expert",
                 pin="1002", certifications="Excavator L3, Dozer L2"),
        Operator(operator_id="OP1003", name="Ravi Verma", skill="Beginner",
                 pin="1003", certifications="Excavator L1"),
    ])
    db.add_all([
        Machine(machine_id="EXC001", model="CAT 320", machine_type="Excavator",
                age_years=3.0, engine_hours=1530.2, status="Available"),
        Machine(machine_id="EXC002", model="CAT 336", machine_type="Excavator",
                age_years=5.0, engine_hours=4210.7, status="Available"),
        Machine(machine_id="LOD001", model="CAT 950M", machine_type="Wheel Loader",
                age_years=6.0, engine_hours=5890.1, status="Maintenance"),
    ])

    # ---- Dataset 1: load verbatim ----
    tdf = pd.read_csv(DATA_DIR / "machine_telemetry.csv")
    for _, r in tdf.iterrows():
        db.add(Telemetry(
            timestamp=datetime.strptime(r["Timestamp"], "%Y-%m-%d %H:%M:%S"),
            machine_id=r["Machine ID"], operator_id=r["Operator ID"],
            engine_hours=float(r["Engine Hours"]), fuel_used=float(r["Fuel Used (L)"]),
            load_cycles=int(r["Load Cycles"]), idling_time=float(r["Idling Time (min)"]),
            seatbelt_status=r["Seatbelt Status"],
            safety_alert_triggered=r["Safety Alert Triggered"],
            proximity_m=None, source="dataset"))

    # Normal-behaviour baseline rows (simulated, labelled) so statistics are meaningful.
    ts = datetime(2025, 4, 20, 8, 0)
    eh = 1498.0
    for _ in range(12):
        ts += timedelta(hours=rng.choice([2, 3, 4]))
        eh += rng.uniform(1.2, 2.4)
        db.add(Telemetry(
            timestamp=ts, machine_id="EXC001", operator_id="OP1001",
            engine_hours=round(eh, 1), fuel_used=round(rng.uniform(4.0, 7.5), 1),
            load_cycles=rng.randint(8, 16), idling_time=float(rng.randint(8, 28)),
            seatbelt_status="Fastened", safety_alert_triggered="No",
            proximity_m=None, source="simulated"))

    # ---- Dataset 2: load verbatim ----
    hdf = pd.read_csv(DATA_DIR / "task_records.csv")
    for _, r in hdf.iterrows():
        db.add(TaskHistory(
            task_id=r["Task ID"], task_type=r["Task Type"], weather=r["Weather"],
            operator_skill=r["Operator Skill"], machine_age=float(r["Machine Age (yrs)"]),
            estimated_time=float(r["Estimated Time (min)"]),
            actual_time=float(r["Actual Time (min)"]), source="dataset"))
    db.commit()
    _seed_synthetic_history(db, rng)
    _seed_demo_tasks_and_modules(db)
    db.commit()
    db.close()


if __name__ == "__main__":
    reset_and_seed()
    print("Database seeded.")


def _seed_synthetic_history(db, rng):
    """Synthetic task-history rows for the ML pipeline (source='synthetic')."""
    skills = list(SKILL_FACTOR)
    weathers = list(WEATHER_FACTOR)
    n = 0
    for ttype, base in BASE_MINUTES.items():
        for _ in range(10):
            n += 1
            w, s = rng.choice(weathers), rng.choice(skills)
            age = rng.randint(1, 8)
            age_factor = 1 + 0.015 * age
            actual = base * WEATHER_FACTOR[w] * SKILL_FACTOR[s] * age_factor + rng.gauss(0, 3)
            est = base * WEATHER_FACTOR[w] * age_factor  # planner ignores skill
            db.add(TaskHistory(
                task_id=f"S{n:03d}", task_type=ttype, weather=w, operator_skill=s,
                machine_age=float(age), estimated_time=round(est, 1),
                actual_time=round(max(actual, 5), 1), source="synthetic"))


def _seed_demo_tasks_and_modules(db):
    today = date.today().isoformat()
    demo_tasks = [
        ("D001", "OP1001", "EXC001", "Earth Excavation", "Sunny",  "Site A - Zone 4", 60),
        ("D002", "OP1001", "EXC001", "Trenching",        "Cloudy", "Site A - Zone 2", 45),
        ("D003", "OP1001", "EXC001", "Material Loading", "Rainy",  "Site B - Depot",  30),
        ("D004", "OP1001", "EXC001", "Grading",          "Sunny",  "Site A - Zone 7", 35),
    ]
    for code, op, mac, ttype, w, site, est in demo_tasks:
        db.add(ScheduledTask(task_code=code, operator_id=op, machine_id=mac,
                             task_type=ttype, weather=w, site=site,
                             scheduled_date=today, estimated_time=est))

    db.add_all([
        TrainingModule(code="TM-SEATBELT", title="Seatbelt Safety & ROPS Awareness",
                       category="Safety", format="e-learning", duration_min=20,
                       description="Why seatbelts + rollover protective structures save lives; "
                                   "pre-start checks and compliance policy."),
        TrainingModule(code="TM-IDLE", title="Efficient Idle Management",
                       category="Efficiency", format="e-learning", duration_min=25,
                       description="Cost of idling, auto-shutdown features, planning work "
                                   "cycles to keep the machine productive."),
        TrainingModule(code="TM-SAFEOP", title="Safe Machine Operation Fundamentals",
                       category="Safety", format="simulation", duration_min=45,
                       description="Simulator scenarios covering safe digging, loading, swing "
                                   "control and stable travel."),
        TrainingModule(code="TM-PROX", title="Proximity Awareness & Blind Spots",
                       category="Safety", format="instructor", duration_min=60,
                       description="Instructor-led session on pedestrian detection, spotter "
                                   "coordination and camera/radar aids."),
        TrainingModule(code="TM-FUEL", title="Fuel-Efficient Operation",
                       category="Efficiency", format="e-learning", duration_min=30,
                       description="Throttle discipline, eco modes and matching machine "
                                   "settings to the task."),
        TrainingModule(code="TM-WEATHER", title="Operating in Adverse Weather",
                       category="Safety", format="e-learning", duration_min=20,
                       description="Rain, wind and low-visibility procedures; adjusted "
                                   "stopping distances and hazard thresholds."),
    ])
