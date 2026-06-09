from fastapi import APIRouter, Request
from app.routes.session import sessions
from app.database.database import SessionLocal
from app.models.game_result_model import GameResult

router = APIRouter()


@router.post("/join")
async def join_game(data: dict):
    pin = data.get("pin", "")
    username = data.get("username", "").strip()

    if not pin or not username:
        return {"valid": False, "message": "PIN and username are required"}

    if pin not in sessions:
        return {"valid": False, "message": "Invalid PIN — session not found"}

    if sessions[pin]["phase"] not in ("lobby", "playing"):
        return {"valid": False, "message": "Session is no longer accepting players"}

    return {"valid": True, "pin": pin}


@router.get("/{username}/history")
def get_player_history(username: str):
    """Return full game history for a player."""
    db = SessionLocal()
    try:
        results = (
            db.query(GameResult)
            .filter(GameResult.username == username)
            .order_by(GameResult.finished_at.desc())
            .all()
        )
        return {
            "username": username,
            "games_played": len(results),
            "history": [
                {
                    "pin": r.pin,
                    "score": r.score,
                    "rank": r.rank,
                    "total_players": r.total_players,
                    "finished_at": r.finished_at.isoformat(),
                }
                for r in results
            ],
        }
    finally:
        db.close()
