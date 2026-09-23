"""CAT Smart Operator Companion - FastAPI entrypoint."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import DB_PATH, SessionLocal
from .routers import (assistant, auth, behavior, dashboard, history, incidents,
                      prediction, safety, tasks, training)
from .seed import reset_and_seed
from .services import simulator, time_prediction

app = FastAPI(title="CAT Smart Operator Companion",
              description="Hackathon prototype: intelligent operator assistant for "
                          "CAT machinery (tasks, safety, behavior, prediction, training).",
              version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.on_event("startup")
def startup():
    if not DB_PATH.exists():
        reset_and_seed()
    db = SessionLocal()
    try:
        time_prediction.train(db)   # train ML pipeline at boot
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "model": time_prediction.model_info()}


@app.post("/api/admin/reseed")
def reseed():
    """Demo utility: reset DB to the pristine seeded state."""
    simulator.clear_sessions()  # drop live simulated telemetry sessions too
    reset_and_seed()
    db = SessionLocal()
    try:
        meta = time_prediction.train(db)
    finally:
        db.close()
    return {"reseeded": True, "model": meta}


for r in (auth, dashboard, tasks, safety, behavior, prediction, training,
          incidents, assistant, history):
    app.include_router(r.router)
