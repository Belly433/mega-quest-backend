from fastapi import APIRouter

router = APIRouter()

questions_db = {}

@router.post("/{quiz_id}")
async def add_question(quiz_id: int, question: dict):
    print("QUESTION RECEIVED =", question)

    if quiz_id not in questions_db:
        questions_db[quiz_id] = []

    questions_db[quiz_id].append(question)

    return {
        "message": "Question added"
    }