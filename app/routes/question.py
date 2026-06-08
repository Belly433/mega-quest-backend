from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.models.question_model import Question

router = APIRouter()


@router.post("/{quiz_id}")
def add_question(quiz_id: int, question: dict, db: Session = Depends(get_db)):
    new_q = Question(
        quiz_id=quiz_id,
        text=question["text"],
        options=question["options"],
        correct_index=question["correctIndex"],
        time_limit=question.get("timeLimit", 20),
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return {"message": "Question added", "id": new_q.id}


@router.get("/{quiz_id}")
def get_questions(quiz_id: int, db: Session = Depends(get_db)):
    qs = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    return [
        {
            "id": q.id,
            "text": q.text,
            "options": q.options,
            "correctIndex": q.correct_index,
            "timeLimit": q.time_limit,
        }
        for q in qs
    ]
