import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database.database import SessionLocal
from app.models.question_model import Question

router = APIRouter()

# ── In-memory game state ──────────────────────────────────────────────────────
# sessions[pin] = {
#   quiz_id, phase, questions, current_index,
#   players: {username: {score, answers: {q_id: answer_index}}},
#   current_answers: {username: {index, time_taken}}
# }
sessions: dict = {}

# connections[pin] = {host: WebSocket|None, players: {username: WebSocket}}
connections: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _question_payload(q: Question, index: int, total: int) -> dict:
    return {
        "id": q.id,
        "text": q.text,
        "options": q.options,
        "correctIndex": q.correct_index,
        "timeLimit": q.time_limit,
        "index": index,
        "total": total,
    }


async def _send(ws: WebSocket, msg: dict):
    try:
        await ws.send_json(msg)
    except Exception:
        pass


async def _broadcast_all(pin: str, msg: dict):
    c = connections.get(pin, {})
    if c.get("host"):
        await _send(c["host"], msg)
    for ws in c.get("players", {}).values():
        await _send(ws, msg)


async def _send_host(pin: str, msg: dict):
    c = connections.get(pin, {})
    if c.get("host"):
        await _send(c["host"], msg)


def _leaderboard(pin: str) -> list:
    players = sessions.get(pin, {}).get("players", {})
    board = [{"username": k, "score": v["score"]} for k, v in players.items()]
    board.sort(key=lambda x: x["score"], reverse=True)
    for i, entry in enumerate(board):
        entry["rank"] = i + 1
    return board


def _calc_score(correct: bool, time_taken: float, time_limit: int) -> int:
    if not correct:
        return 0
    bonus = int(max(0, (time_limit - time_taken) / time_limit) * 500)
    return 1000 + bonus


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@router.post("/create")
async def create_session(data: dict):
    pin = str(random.randint(100000, 999999))
    while pin in sessions:
        pin = str(random.randint(100000, 999999))

    sessions[pin] = {
        "quiz_id": data["quiz_id"],
        "phase": "lobby",
        "questions": [],
        "current_index": -1,
        "players": {},
        "current_answers": {},
    }
    connections[pin] = {"host": None, "players": {}}
    return {"pin": pin}


@router.get("/{pin}/leaderboard")
async def get_leaderboard(pin: str):
    if pin not in sessions:
        return {"error": "Session not found"}
    return _leaderboard(pin)


@router.get("/{pin}")
async def get_session(pin: str):
    session = sessions.get(pin)
    if not session:
        return {"error": "Session not found"}
    return {
        "pin": pin,
        "phase": session["phase"],
        "players": list(session["players"].keys()),
    }


# ── Host WebSocket ─────────────────────────────────────────────────────────────
# Messages from host:
#   {type: "start_quiz"}
#   {type: "next_question"}
#   {type: "end_quiz"}

@router.websocket("/ws/host/{pin}")
async def host_ws(websocket: WebSocket, pin: str, quiz_id: int = 0):
    await websocket.accept()

    if pin not in sessions:
        if quiz_id:
            sessions[pin] = {
                "quiz_id": quiz_id,
                "phase": "lobby",
                "questions": [],
                "current_index": -1,
                "players": {},
                "current_answers": {},
            }
            connections[pin] = {"host": None, "players": {}}
        else:
            await websocket.send_json({"type": "error", "message": "Session expired. Go back to dashboard and click Host again."})
            await websocket.close(code=4004)
            return

    connections[pin]["host"] = websocket

    await _send(websocket, {
        "type": "player_list",
        "players": list(sessions[pin]["players"].keys()),
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_quiz":
                session = sessions[pin]
                if session["phase"] != "lobby":
                    continue

                db = SessionLocal()
                try:
                    qs = db.query(Question).filter(
                        Question.quiz_id == session["quiz_id"]
                    ).all()
                    qs = list(qs)
                finally:
                    db.close()

                if not qs:
                    await _send(websocket, {
                        "type": "error",
                        "message": "No questions found for this quiz. Add questions first.",
                    })
                    continue

                session["questions"] = qs
                session["current_index"] = 0
                session["phase"] = "playing"
                session["current_answers"] = {}

                q = qs[0]
                full = _question_payload(q, 0, len(qs))
                safe = {k: v for k, v in full.items() if k != "correctIndex"}

                await _send(websocket, {"type": "question", **full})
                for ws in connections[pin].get("players", {}).values():
                    await _send(ws, {"type": "question", **safe})

            elif msg_type == "next_question":
                session = sessions[pin]
                if session["phase"] != "playing":
                    continue

                qs = session["questions"]
                next_idx = session["current_index"] + 1

                if next_idx >= len(qs):
                    session["phase"] = "finished"
                    board = _leaderboard(pin)
                    await _broadcast_all(pin, {
                        "type": "game_over",
                        "leaderboard": board,
                        "pin": pin,
                    })
                else:
                    session["current_index"] = next_idx
                    session["current_answers"] = {}
                    q = qs[next_idx]
                    full = _question_payload(q, next_idx, len(qs))
                    safe = {k: v for k, v in full.items() if k != "correctIndex"}

                    await _send(websocket, {"type": "question", **full})
                    for ws in connections[pin].get("players", {}).values():
                        await _send(ws, {"type": "question", **safe})

            elif msg_type == "end_quiz":
                session = sessions[pin]
                session["phase"] = "finished"
                board = _leaderboard(pin)
                await _broadcast_all(pin, {
                    "type": "game_over",
                    "leaderboard": board,
                    "pin": pin,
                })

    except WebSocketDisconnect:
        connections[pin]["host"] = None
    except Exception as e:
        print(f"[host_ws error] pin={pin} error={e}")
        connections[pin]["host"] = None


# ── Player WebSocket ───────────────────────────────────────────────────────────
# First message:  {type: "player_connect", username: "..."}
# Answer:         {type: "answer", username: "...", answer_index: 0, time_taken: 5.3}

@router.websocket("/ws/player/{pin}")
async def player_ws(websocket: WebSocket, pin: str):
    await websocket.accept()

    if pin not in sessions:
        await websocket.send_json({"type": "error", "message": "Session not found. Ask the host for a valid PIN."})
        await websocket.close(code=4004)
        return
    username: str | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "player_connect":
                username = data.get("username", "").strip()
                if not username:
                    await _send(websocket, {"type": "error", "message": "Username required"})
                    continue

                session = sessions[pin]
                if username not in session["players"]:
                    session["players"][username] = {"score": 0, "answers": {}}

                connections[pin]["players"][username] = websocket

                await _send(websocket, {
                    "type": "joined",
                    "username": username,
                    "phase": session["phase"],
                })

                # If game already in progress, send current question
                if session["phase"] == "playing" and session["current_index"] >= 0:
                    q = session["questions"][session["current_index"]]
                    full = _question_payload(
                        q, session["current_index"], len(session["questions"])
                    )
                    safe = {k: v for k, v in full.items() if k != "correctIndex"}
                    await _send(websocket, {"type": "question", **safe})

                # Notify host
                await _send_host(pin, {
                    "type": "player_list",
                    "players": list(sessions[pin]["players"].keys()),
                })

            elif msg_type == "tab_switch" and username:
                count = int(data.get("count", 1))
                await _send_host(pin, {
                    "type": "cheat_warning",
                    "username": username,
                    "count": count,
                })

            elif msg_type == "answer" and username:
                session = sessions[pin]
                if session["phase"] != "playing":
                    continue

                idx = session["current_index"]
                if idx < 0 or idx >= len(session["questions"]):
                    continue

                # Prevent double-answering this question
                if username in session["current_answers"]:
                    continue

                q = session["questions"][idx]
                answer_index = int(data.get("answer_index", -1))
                time_taken = float(data.get("time_taken", q.time_limit))

                correct = answer_index == q.correct_index
                points = _calc_score(correct, time_taken, q.time_limit)
                session["players"][username]["score"] += points
                session["players"][username]["answers"][idx] = answer_index
                session["current_answers"][username] = {
                    "index": answer_index,
                    "time_taken": time_taken,
                }

                await _send(websocket, {
                    "type": "answer_result",
                    "correct": correct,
                    "correct_index": q.correct_index,
                    "points": points,
                    "total_score": session["players"][username]["score"],
                })

                answered = len(session["current_answers"])
                total_players = len(session["players"])
                await _send_host(pin, {
                    "type": "answer_count",
                    "answered": answered,
                    "total": total_players,
                    "question_index": idx,
                })

                # Auto-advance when all players have answered
                if answered >= total_players:
                    qs = session["questions"]
                    next_idx = idx + 1
                    if next_idx >= len(qs):
                        session["phase"] = "finished"
                        board = _leaderboard(pin)
                        await _broadcast_all(pin, {
                            "type": "game_over",
                            "leaderboard": board,
                            "pin": pin,
                        })
                    else:
                        session["current_index"] = next_idx
                        session["current_answers"] = {}
                        q = qs[next_idx]
                        full = _question_payload(q, next_idx, len(qs))
                        safe = {k: v for k, v in full.items() if k != "correctIndex"}
                        await _send_host(pin, {"type": "question", **full})
                        for ws in connections[pin].get("players", {}).values():
                            await _send(ws, {"type": "question", **safe})

    except WebSocketDisconnect:
        if username and pin in connections:
            connections[pin]["players"].pop(username, None)
