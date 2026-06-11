from fastapi import FastAPI, HTTPException, Depends
from typing import Annotated, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from db.database import SessionLocal, engine
from models.user import Users
from db.database import Base
from fastapi.middleware.cors import CORSMiddleware
from schemas.orders_position import Orders_position_Base, Orders_position_Model
from routers.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from routers.mould import router as mould_router
from routers.moulds_tpm import router as moulds_tpm_router
from routers.moulds_book import router as moulds_book_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from routers.changeovers import router as changeovers_router
from models.changeovers import Changeover  # ważne przed create_all
from routers.changeovers import router as changeovers_router
from routers.changeovers_log import router as changeovers_log_router
from models.calendar import CalendarEntry  # wa‘•ne przed create_all
from routers.calendar import router as calendar_router
from models.calendar_log import CalendarLog  # wa‘•ne przed create_all
from routers.calendar_log import router as calendar_log_router
from models.production import MachineGroup, MachineStatus, OrderType, ProductionOrder, ProductionTask, Workstation, Operation, OperationLog
from routers.production import router as production_router
from routers.service import router as service_router
from routers.current_sv import router as current_sv_router
from models.analytics import AnalyticaWorkers, AnalyticaMachines, AnalyticaService  # before create_all
from routers.analytics import router as analytics_router
from models.mes_session import MesSessionLog  # before create_all
from routers.mes_session import router as mes_session_router
from models.service_guide import ServiceGuide, ServiceGuideStep  # before create_all
from routers.service_guides import router as service_guides_router

app = FastAPI()

Path("../media").mkdir(parents=True, exist_ok=True)
Path("../media/book").mkdir(parents=True, exist_ok=True)
Path("../media/tpm").mkdir(parents=True, exist_ok=True)
Path("../media/service_guides").mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory="media"), name="media")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # "http://localhost:8000",
    # "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://10.10.77.75:5173",
    "http://10.10.77.75:4173",
    "http://192.168.1.29:5173",
]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )
       
Base.metadata.create_all(bind=engine)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE service_guides ADD COLUMN IF NOT EXISTS mould_id INTEGER"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_service_guides_mould_id ON service_guides (mould_id)"))
    conn.execute(text("ALTER TABLE service_guide_steps ADD COLUMN IF NOT EXISTS extra_photo_1 TEXT"))
    conn.execute(text("ALTER TABLE service_guide_steps ADD COLUMN IF NOT EXISTS extra_photo_2 TEXT"))

app.include_router(auth_router)
app.include_router(mould_router)
app.include_router(moulds_tpm_router)
app.include_router(moulds_book_router)
app.include_router(changeovers_router)
app.include_router(changeovers_log_router)
app.include_router(calendar_router)
app.include_router(calendar_log_router)
app.include_router(production_router)
app.include_router(service_router)
app.include_router(current_sv_router)
app.include_router(analytics_router)
app.include_router(mes_session_router)
app.include_router(service_guides_router)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
