import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from datetime import datetime
from app.database.database import SessionLocal
from app.models.question_model import Question
from app.models.game_session_model import GameSession
from app.models.tab_switch_model import TabSwitchEvent
from app.models.game_result_model import GameResult

router = APIRouter()

# ── In-memory game state ──────────────────────────────────────────────────────
sessions: dict = {}
connections: dict = {}


# ── DB persistence helpers ────────────────────────────────────────────────────

def _save_session(pin: str):
    session = sessions.get(pin)
    if not session:
        return
    db = SessionLocal()
    try:
        row = db.query(GameSession).filter(GameSession.pin == pin).first()
        if row:
            row.phase = session["phase"]
            row.current_index = session["current_index"]
            row.players = dict(session["players"])
            row.current_answers = dict(session["current_answers"])
        else:
            row = GameSession(
                pin=pin,
                quiz_id=session["quiz_id"],
                phase=session["phase"],
                current_index=session["current_index"],
                players=dict(session["players"]),
                current_answers=dict(session["current_answers"]),
            )
            db.add(row)
        db.commit()
    except Exception as e:
        print(f"[_save_session error] pin={pin} {e}")
        db.rollback()
    finally:
        db.close()


def load_sessions_from_db():
    """Called once at startup to restore non-finished sessions into memory."""
    db = SessionLocal()
    try:
        rows = db.query(GameSession).filter(GameSession.phase != "finished").all()
        for row in rows:
            sessions[row.pin] = {
                "quiz_id": row.quiz_id,
                "phase": row.phase,
                "questions": [],  # reloaded when host reconnects
                "current_index": row.current_index,
                "players": row.players or {},
                "current_answers": row.current_answers or {},
            }
            connections[row.pin] = {"host": None, "players": {}}
        print(f"[startup] Loaded {len(rows)} session(s) from DB")
    except Exception as e:
        print(f"[load_sessions_from_db error] {e}")
    finally:
        db.close()


def _reload_questions(pin: str):
    """Reload question objects for a session that was restored from DB."""
    session = sessions.get(pin)
    if not session or session["questions"]:
        return
    db = SessionLocal()
    try:
        qs = db.query(Question).filter(Question.quiz_id == session["quiz_id"]).all()
        session["questions"] = list(qs)
    except Exception as e:
        print(f"[_reload_questions error] pin={pin} {e}")
    finally:
        db.close()


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def _save_results(pin: str, board: list):
    """Persist final leaderboard to game_results table."""
    db = SessionLocal()
    try:
        total = len(board)
        for entry in board:
            db.add(GameResult(
                pin=pin,
                username=entry["username"],
                score=entry["score"],
                rank=entry["rank"],
                total_players=total,
                finished_at=datetime.utcnow(),
            ))
        db.commit()
    except Exception as e:
        print(f"[_save_results error] {e}")
        db.rollback()
    finally:
        db.close()


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
    _save_session(pin)
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
            _save_session(pin)
        else:
            await websocket.send_json({"type": "error", "message": "Session expired. Go back to dashboard and click Host again."})
            await websocket.close(code=4004)
            return

    # If session was restored from DB, reload questions so the host can resume
    _reload_questions(pin)

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
                _save_session(pin)

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
                    _save_session(pin)
                    _save_results(pin, board)
                    await _broadcast_all(pin, {
                        "type": "game_over",
                        "leaderboard": board,
                        "pin": pin,
                    })
                else:
                    session["current_index"] = next_idx
                    session["current_answers"] = {}
                    _save_session(pin)
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
                _save_session(pin)
                _save_results(pin, board)
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
                    _save_session(pin)

                connections[pin]["players"][username] = websocket

                await _send(websocket, {
                    "type": "joined",
                    "username": username,
                    "phase": session["phase"],
                })

                if session["phase"] == "playing" and session["current_index"] >= 0:
                    _reload_questions(pin)
                    if session["questions"]:
                        q = session["questions"][session["current_index"]]
                        full = _question_payload(
                            q, session["current_index"], len(session["questions"])
                        )
                        safe = {k: v for k, v in full.items() if k != "correctIndex"}
                        await _send(websocket, {"type": "question", **safe})

                await _send_host(pin, {
                    "type": "player_list",
                    "players": list(sessions[pin]["players"].keys()),
                })

            elif msg_type == "tab_switch" and username:
                count = int(data.get("count", 1))
                # Persist event to database
                db = SessionLocal()
                try:
                    db.add(TabSwitchEvent(
                        pin=pin,
                        username=username,
                        switch_count=count,
                        timestamp=datetime.utcnow(),
                    ))
                    db.commit()
                except Exception as e:
                    print(f"[tab_switch save error] {e}")
                    db.rollback()
                finally:
                    db.close()
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

                if username in session["current_answers"]:
                    continue

                q = session["questions"][idx]
                answer_index = int(data.get("answer_index", -1))
                time_taken = float(data.get("time_taken", q.time_limit))

                correct = answer_index == q.correct_index
                points = _calc_score(correct, time_taken, q.time_limit)
                session["players"][username]["score"] += points
                session["players"][username]["answers"][str(idx)] = answer_index
                session["current_answers"][username] = {
                    "index": answer_index,
                    "time_taken": time_taken,
                }
                _save_session(pin)

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

                if answered >= total_players:
                    qs = session["questions"]
                    next_idx = idx + 1
                    if next_idx >= len(qs):
                        session["phase"] = "finished"
                        board = _leaderboard(pin)
                        _save_session(pin)
                        _save_results(pin, board)
                        await _broadcast_all(pin, {
                            "type": "game_over",
                            "leaderboard": board,
                            "pin": pin,
                        })
                    else:
                        session["current_index"] = next_idx
                        session["current_answers"] = {}
                        _save_session(pin)
                        q = qs[next_idx]
                        full = _question_payload(q, next_idx, len(qs))
                        safe = {k: v for k, v in full.items() if k != "correctIndex"}
                        await _send_host(pin, {"type": "question", **full})
                        for ws in connections[pin].get("players", {}).values():
                            await _send(ws, {"type": "question", **safe})

    except WebSocketDisconnect:
        if username and pin in connections:
            connections[pin]["players"].pop(username, None)
