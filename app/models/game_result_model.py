from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database.database import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id = Column(Integer, primary_key=True, index=True)
    pin = Column(String, nullable=False)
    username = Column(String, nullable=False, index=True)
    score = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)
    total_players = Column(Integer, nullable=False)
    finished_at = Column(DateTime, default=datetime.utcnow)
