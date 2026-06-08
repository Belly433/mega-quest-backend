from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket_manager import manager
from app.routes.question import questions_db
import random

router = APIRouter()

sessions = {}

@router.post("/create")
async def create_session(data: dict):

    pin = str(random.randint(100000, 999999))

    sessions[pin] = {
        "players": [],
        "quiz_id": data["quiz_id"]
    }

    return {
        "pin": pin
    }

@router.get("/{pin}")
async def get_session(pin: str):

    session = sessions.get(pin)

    if not session:
        return {"error": "Session not found"}

    quiz_id = session["quiz_id"]

    questions = questions_db.get(quiz_id, [])
    print("QUIZ ID =", quiz_id)
    print("QUESTIONS =", questions)
    return {
        "pin": pin,
        "questions": questions
    }

@router.websocket("/ws/{pin}")
async def websocket_endpoint(websocket: WebSocket, pin: str):

    await manager.connect(pin, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            await manager.broadcast(pin, data)

    except WebSocketDisconnect:
        manager.disconnect(pin, websocket)