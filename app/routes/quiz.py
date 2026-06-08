from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.models.quiz_model import Quiz
from app.models.question_model import Question
from app.schemas.quiz_schema import QuizSchema

router = APIRouter()


@router.post("/create")
def create_quiz(quiz: QuizSchema, db: Session = Depends(get_db)):
    new_quiz = Quiz(title=quiz.title, description=quiz.description)
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    return {"message": "Quiz created", "quiz_id": new_quiz.id, "id": new_quiz.id}


@router.get("/")
def get_quizzes(db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).all()
    result = []
    for q in quizzes:
        count = db.query(Question).filter(Question.quiz_id == q.id).count()
        result.append({
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "questionCount": count,
        })
    return result


@router.get("/{quiz_id}")
def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    qs = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": q.options,
                "correctIndex": q.correct_index,
                "timeLimit": q.time_limit,
            }
            for q in qs
        ],
    }
