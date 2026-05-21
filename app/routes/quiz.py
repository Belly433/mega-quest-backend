from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.models.quiz_model import Quiz
from app.schemas.quiz_schema import QuizSchema

router = APIRouter()

@router.post("/create")
def create_quiz(quiz: QuizSchema, db: Session = Depends(get_db)):

    new_quiz = Quiz(
        title=quiz.title,
        description=quiz.description
    )

    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    return {
        "message": "Quiz created",
        "quiz_id": new_quiz.id
    }

@router.get("/")
def get_quizzes(db: Session = Depends(get_db)):

    quizzes = db.query(Quiz).all()

    return quizzes