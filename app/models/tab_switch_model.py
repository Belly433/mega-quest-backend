from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database.database import Base


class TabSwitchEvent(Base):
    __tablename__ = "tab_switch_events"

    id = Column(Integer, primary_key=True, index=True)
    pin = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    switch_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
