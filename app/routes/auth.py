from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.auth_schema import RegisterSchema, LoginSchema
from app.database.dependencies import get_db
from app.models.user_model import User

router = APIRouter()

@router.get("/test")
def test_auth():
    return {"message": "Auth route works"}

@router.post("/register")
def register(user: RegisterSchema, db: Session = Depends(get_db)):

    new_user = User(
        username=user.username,
        email=user.email,
        password=user.password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully",
        "user_id": new_user.id
    }

@router.post("/login")
def login(user: LoginSchema, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()

    if not existing_user:
        return {"message": "User not found"}

    if existing_user.password != user.password:
        return {"message": "Incorrect password"}

    return {
        "message": "Login successful",
        "user_id": existing_user.id,
        "username": existing_user.username
    }