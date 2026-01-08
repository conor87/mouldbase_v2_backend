from fastapi import FastAPI, HTTPException, Depends
from typing import Annotated, List
from sqlalchemy.orm import Session
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

app = FastAPI()

Path("../media").mkdir(parents=True, exist_ok=True)
Path("../media/book").mkdir(parents=True, exist_ok=True)
Path("../media/tpm").mkdir(parents=True, exist_ok=True)

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

app.include_router(auth_router)
app.include_router(mould_router)
app.include_router(moulds_tpm_router)
app.include_router(moulds_book_router)
app.include_router(changeovers_router)
app.include_router(changeovers_log_router)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)