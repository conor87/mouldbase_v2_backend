from fastapi import FastAPI, HTTPException, Depends
from typing import Annotated, List
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import SessionLocal, engine
from models.orders_position import Orders_position
from models.company import Company
from models.user import Users
from db.database import Base
from fastapi.middleware.cors import CORSMiddleware
from schemas.orders_position import Orders_position_Base, Orders_position_Model
from routers.orders_position import router as orders_positions_router
from routers.company import router as company_router
from routers.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    'http://localhost:3000'
]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )
       
Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(orders_positions_router)
app.include_router(company_router)

#tests
#zmiana 