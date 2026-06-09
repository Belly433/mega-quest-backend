from sqlalchemy import Column, Integer, String, JSON
from app.database.database import Base


class GameSession(Base):
    __tablename__ = "game_sessions"

    pin = Column(String, primary_key=True)
    quiz_id = Column(Integer, nullable=False)
    phase = Column(String, default="lobby")
    current_index = Column(Integer, default=-1)
    players = Column(JSON, default=dict)
    current_answers = Column(JSON, default=dict)
