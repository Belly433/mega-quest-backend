import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database.database import engine, Base
from app.models.user_model import User       # noqa: F401 — ensures table is created
from app.models.quiz_model import Quiz       # noqa: F401
from app.models.question_model import Question  # noqa: F401
from app.models.game_session_model import GameSession  # noqa: F401
from app.models.tab_switch_model import TabSwitchEvent  # noqa: F401
from app.models.game_result_model import GameResult  # noqa: F401
from app.routes import auth, quiz, question, session, player, anti_cheat

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Mega Quest API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def startup_event():
    from app.routes.session import load_sessions_from_db
    load_sessions_from_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
