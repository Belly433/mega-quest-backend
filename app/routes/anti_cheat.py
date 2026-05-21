from fastapi import APIRouter
from app.services.redis_service import redis_client

router = APIRouter()

@router.post("/flag/{user_id}")
def flag_user(user_id: int):

    redis_client.set(f"cheater:{user_id}", "true")

    return {
        "message": f"User {user_id} flagged for cheating"
    }

@router.get("/check/{user_id}")
def check_user(user_id: int):

    flagged = redis_client.get(f"cheater:{user_id}")

    return {
        "user_id": user_id,
        "flagged": flagged
    }