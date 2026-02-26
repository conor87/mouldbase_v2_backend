from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from fastapi import Depends
from typing import Annotated
from sqlalchemy.orm import Session

# ZMIANA: URL PostgreSQL
# URL_DATABASE = "postgresql+psycopg2://postgres:228100@192.168.88.115:5432/mouldbase" #home
URL_DATABASE = "postgresql+psycopg2://postgres:228100@localhost:5432/mouldbase" #home2
#URL_DATABASE = "postgresql+psycopg2://postgres:123456@10.10.77.75:5432/mouldbase" #lamela

engine = create_engine(
    URL_DATABASE,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
