from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ============ User Schemas ============

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    phone: Optional[str] = None
    created_at: datetime
    is_active: bool
    email_verified: bool = False
    
    class Config:
        from_attributes = True  # Pydantic v2 syntax (also works in v1.10+)

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class ResendVerificationRequest(BaseModel):
    email: EmailStr

# ============ Quiz Schemas ============

class QuestionAnswer(BaseModel):
    question: str
    answer: Optional[str] = None
    answers: Optional[List[str]] = None  # For multi-select questions

class ScenarioData(BaseModel):
    question: str
    answer: Optional[str] = None

class QuizSaveRequest(BaseModel):
    sessionId: str
    scenario: Optional[ScenarioData] = None
    questionsAndAnswers: List[QuestionAnswer] = []
    timestamp: str

class QuizSaveResponse(BaseModel):
    success: bool
    message: str
    sessionId: str

class QuizDataResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class QuizSubmitRequest(BaseModel):
    sessionId: str

class QuizSubmitResponse(BaseModel):
    success: bool
    message: str
    status: str
    recommendations: Optional[Dict[str, Any]] = None
