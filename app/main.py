from fastapi import FastAPI
from app.routes import auth
from app.database.database import engine, Base
from app.models.user_model import User

app = FastAPI()
Base.metadata.create_all(bind=engine)

app.include_router(auth.router, prefix="/auth")

@app.get("/")
def home():
    return {"message": "Mega Quest API running"}