"""SQLAlchemy models. Field names mirror the two supplied datasets."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .database import Base


class Operator(Base):
    __tablename__ = "operators"
    id = Column(Integer, primary_key=True)
    operator_id = Column(String, unique=True, index=True)
    name = Column(String)
    skill = Column(String)  # Beginner / Intermediate / Expert
    pin = Column(String)
    certifications = Column(String, default="")


class Machine(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True)
    machine_id = Column(String, unique=True, index=True)
    model = Column(String)
    machine_type = Column(String)
    age_years = Column(Float)
    engine_hours = Column(Float)
    status = Column(String, default="Available")


class Telemetry(Base):
    """Dataset 1: machine/operator usage telemetry."""
    __tablename__ = "telemetry"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    machine_id = Column(String, index=True)
    operator_id = Column(String, index=True)
    engine_hours = Column(Float)
    fuel_used = Column(Float)
    load_cycles = Column(Integer)
    idling_time = Column(Float)
    seatbelt_status = Column(String)
    safety_alert_triggered = Column(String)
    proximity_m = Column(Float, nullable=True)   # assumed sensor (not in dataset)
    source = Column(String, default="dataset")   # dataset | simulated


class TaskHistory(Base):
    """Dataset 2: historical task records used to train time estimation."""
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    task_id = Column(String, index=True)
    task_type = Column(String)
    weather = Column(String)
    operator_skill = Column(String)
    machine_age = Column(Float)
    estimated_time = Column(Float)
    actual_time = Column(Float)
    source = Column(String, default="dataset")   # dataset | synthetic


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True)
    task_code = Column(String, unique=True, index=True)
    operator_id = Column(String, index=True)
    machine_id = Column(String)
    task_type = Column(String)
    weather = Column(String)
    site = Column(String, default="Site A")
    scheduled_date = Column(String)
    shift_start = Column(String, default="08:00")
    status = Column(String, default="Scheduled")  # Scheduled / In Progress / Completed
    estimated_time = Column(Float)
    predicted_time = Column(Float, nullable=True)
    actual_time = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    operator_id = Column(String, index=True)
    machine_id = Column(String)
    task_code = Column(String, nullable=True)
    incident_type = Column(String)
    severity = Column(String)  # INFO / WARNING / CRITICAL
    description = Column(Text)
    status = Column(String, default="Open")  # Open / Acknowledged / Resolved
    action_taken = Column(String, default="")
    source = Column(String, default="system")


class TrainingModule(Base):
    __tablename__ = "training_modules"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    title = Column(String)
    category = Column(String)
    format = Column(String)  # e-learning / simulation / instructor
    duration_min = Column(Integer)
    description = Column(Text)


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"
    id = Column(Integer, primary_key=True)
    operator_id = Column(String, index=True)
    module_code = Column(String)
    reason = Column(Text)
    status = Column(String, default="Assigned")  # Assigned / Completed
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
