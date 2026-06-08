from fastapi import FastAPI
from app.routes import auth
from app.database.database import engine, Base
from app.models.user_model import User
from app.models.quiz_model import Quiz
from app.routes import quiz
from app.routes import anti_cheat
from fastapi.middleware.cors import CORSMiddleware
from app.routes import session
from app.routes import question
from app.routes import player
app = FastAPI()
Base.metadata.create_all(bind=engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/auth")
app.include_router(quiz.router, prefix="/quiz")
app.include_router(anti_cheat.router, prefix="/anti-cheat")
app.include_router(session.router, prefix="/session")
app.include_router(player.router, prefix="/player")
app.include_router(
    question.router,
    prefix="/question"
)

@app.get("/")
def home():
    return {"message": "Mega Quest API running"}