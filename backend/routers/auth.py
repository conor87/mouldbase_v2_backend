# routers/auth.py
from datetime import timedelta
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session
from starlette import status
from sqlalchemy.exc import IntegrityError

from db.database import SessionLocal
from models.user import Users
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError


router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "secret"
ALGORITHM = "HS256"

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2bearer = OAuth2PasswordBearer(tokenUrl="auth/token")


class CreateUserRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserOut(CreateUserRequest):
    password: SecretStr = Field(hidden=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id, "role": role}
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        role: str = payload.get("role")

        if username is None or user_id is None or role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

        return {"username": username, "id": user_id, "role": role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")


user_dependency = Annotated[dict, Depends(get_current_user)]


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: user_dependency):
        if user.get("role") not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Niewystarczające uprawnienia",
            )


user_required = RoleChecker(["user", "userdn", "admin", "admindn", "superadmin"])
admin_required = RoleChecker(["admin", "admindn", "superadmin"])
superadmin_required = RoleChecker(["superadmin"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    existing_user = db.query(Users).filter(Users.username == create_user_request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o takiej nazwie już istnieje.",
        )

    create_user_model = Users(
        username=create_user_request.username,
        hashed_password=bcrypt_context.hash(create_user_request.password),
    )

    db.add(create_user_model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o takiej nazwie już istnieje.",
        )

    return {"message": f"User {create_user_request.username} added"}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency,
):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

    token = create_access_token(
        user.username,
        user.id,
        user.role,
        timedelta(hours=1),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def read_me(user: user_dependency):
    return user
