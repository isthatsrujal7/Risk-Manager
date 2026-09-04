from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password, get_current_user
from app.models.database import get_db
from app.models.models import User
from app.schemas.schemas import LoginRequest, UserOut

router = APIRouter()


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.username, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut(username=user.username, role=user.role, display_name=user.display_name).model_dump(),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return UserOut(username=user.username, role=user.role, display_name=user.display_name).model_dump()