import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import engine, Base
from app.models.user_model import User       # noqa: F401 — ensures table is created
from app.models.quiz_model import Quiz       # noqa: F401
from app.models.question_model import Question  # noqa: F401

from app.models.game_session_model import GameSession  # noqa: F401 — ensures table is created
from app.models.tab_switch_model import TabSwitchEvent  # noqa: F401 — ensures table is created
from app.routes import auth, quiz, question, session, player, anti_cheat

app = FastAPI(title="Mega Quest API")

Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def startup_event():
    from app.routes.session import load_sessions_from_db
    load_sessions_from_db()

# CORS — allow the frontend origin (set ALLOWED_ORIGINS in prod)
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8080,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # wildcard — credentials not used, so this is safe
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(quiz.router, prefix="/quiz")
app.include_router(question.router, prefix="/question")
app.include_router(session.router, prefix="/session")
app.include_router(player.router, prefix="/player")
app.include_router(anti_cheat.router, prefix="/anti-cheat")


@app.get("/")
def home():
    return {"message": "Mega Quest API running"}
