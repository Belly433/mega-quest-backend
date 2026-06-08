from fastapi import APIRouter
from app.routes.session import sessions

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
