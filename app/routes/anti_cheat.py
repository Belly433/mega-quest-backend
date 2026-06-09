from fastapi import APIRouter
from app.database.database import SessionLocal
from app.models.tab_switch_model import TabSwitchEvent

router = APIRouter()

SUSPICIOUS_THRESHOLD = 3


@router.get("/{pin}/suspicious_activity")
def get_suspicious_activity(pin: str, threshold: int = SUSPICIOUS_THRESHOLD):
    """
    Returns tab-switch activity per player for a session.
    A player is flagged if their total switch count >= threshold.
    """
    db = SessionLocal()
    try:
        events = (
            db.query(TabSwitchEvent)
            .filter(TabSwitchEvent.pin == pin)
            .order_by(TabSwitchEvent.username, TabSwitchEvent.timestamp)
            .all()
        )

        # Group events by username
        players: dict[str, list] = {}
        for ev in events:
            players.setdefault(ev.username, []).append(ev)

        result = []
        for username, evs in players.items():
            max_count = max(e.switch_count for e in evs)
            result.append({
                "username": username,
                "switch_count": max_count,
                "flagged": max_count >= threshold,
                "events": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "count": e.switch_count,
                    }
                    for e in evs
                ],
            })

        return {
            "pin": pin,
            "threshold": threshold,
            "players": result,
        }
    finally:
        db.close()
