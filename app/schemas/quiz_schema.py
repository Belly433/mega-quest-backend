from pydantic import BaseModel

class QuizSchema(BaseModel):
    title: str
    description: str