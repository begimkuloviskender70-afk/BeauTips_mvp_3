from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
import uuid
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from database import get_db, engine, Base
from models import User, QuizSession, QuizAnswer
from schemas import (
    UserCreate, UserLogin, UserResponse, Token,
    QuizSaveRequest, QuizSaveResponse, QuizDataResponse,
    QuizSubmitRequest, QuizSubmitResponse
)
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from routers.auth_router import router as auth_router
from routers.history_router import router as history_router

from exceptions import (
    BeauTipsException,
    SessionNotFoundError,
    AnswersNotFoundError,
)

app = FastAPI(title="Beautips API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(history_router)

# Mount static files - everything is now in frontend/
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists() and frontend_path.is_dir():
    try:
        app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
        logging.info(f"✓ Mounted static files from {frontend_path}")
    except Exception as e:
        logging.warning(f"Could not mount static files: {e}")
else:
    logging.warning("Frontend directory not found - running in API-only mode")

# Create tables on startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ============ Test Endpoint ============

@app.get("/api/test/schema")
async def test_schema():
    """Test endpoint to verify schema"""
    from schemas import UserCreate
    return {
        "UserCreate_fields": list(UserCreate.model_fields.keys()),
        "has_phone": "phone" in UserCreate.model_fields
    }

# ============ Authentication Endpoints (Moved to routers/auth_router.py) ============

# ============ Quiz Endpoints ============

@app.post("/api/quiz/save", response_model=QuizSaveResponse)
async def save_quiz_answers(
    quiz_data: QuizSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save or update quiz answers"""
    try:
        print(f"📥 SAVE QUIZ - Session: {quiz_data.sessionId}, User: {current_user.username}")
        
        # 1. Get or Create Session (Simple)
        result = await db.execute(
            select(QuizSession).where(QuizSession.session_id == quiz_data.sessionId)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            session = QuizSession(
                session_id=quiz_data.sessionId,
                user_id=current_user.id,
                completed=False
            )
            db.add(session)
            # We flush to make it available for the answer record
            try:
                await db.flush()
                print(f"✓ Created new session: {quiz_data.sessionId}")
            except Exception:
                # If it already exists (race condition), just roll back this flush and continue
                await db.rollback()
                # Re-fetch the session
                result = await db.execute(
                    select(QuizSession).where(QuizSession.session_id == quiz_data.sessionId)
                )
                session = result.scalar_one_or_none()
        
        # 2. Prepare Question-Answer data
        qa_data = [qa.model_dump(exclude_none=True) if hasattr(qa, "model_dump") else qa.dict(exclude_none=True) for qa in quiz_data.questionsAndAnswers]
        
        # 3. Handle QuizAnswer (Merge-like behavior)
        result = await db.execute(
            select(QuizAnswer).where(QuizAnswer.session_id == quiz_data.sessionId)
        )
        existing_answer = result.scalar_one_or_none()
        
        if existing_answer:
            if quiz_data.scenario:
                existing_answer.scenario_question = quiz_data.scenario.question
                existing_answer.scenario_answer = quiz_data.scenario.answer
            existing_answer.questions_and_answers = qa_data
            print(f"✓ Updated existing answer")
        else:
            new_answer = QuizAnswer(
                session_id=quiz_data.sessionId,
                user_id=current_user.id,
                scenario_question=quiz_data.scenario.question if quiz_data.scenario else None,
                scenario_answer=quiz_data.scenario.answer if quiz_data.scenario else None,
                questions_and_answers=qa_data
            )
            db.add(new_answer)
            print(f"✓ Created new answer")
        
        await db.commit()
        print(f"✅ Quiz saved successfully")
        return QuizSaveResponse(
            success=True,
            message="Saved",
            sessionId=quiz_data.sessionId
        )
        
    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR in save_quiz: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/quiz/{session_id}", response_model=QuizDataResponse)
async def get_quiz_answers(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quiz answers by session ID"""
    
    # Get quiz answer
    result = await db.execute(
        select(QuizAnswer).where(
            QuizAnswer.session_id == session_id,
            QuizAnswer.user_id == current_user.id
        )
    )
    answer = result.scalar_one_or_none()
    
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz answers not found"
        )
    
    return QuizDataResponse(
        success=True,
        data={
            "sessionId": answer.session_id,
            "scenario": {
                "question": answer.scenario_question,
                "answer": answer.scenario_answer
            },
            "questionsAndAnswers": answer.questions_and_answers,
            "createdAt": answer.created_at.isoformat(),
            "updatedAt": answer.updated_at.isoformat()
        }
    )

from ai_service import ai_service
from models import AIRecommendation

@app.post("/api/quiz/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    submit_data: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit quiz for AI processing"""
    try:
        print(f"=" * 60)
        print(f"SUBMIT QUIZ - START")
        print(f"Session ID: {submit_data.sessionId}")
        print(f"User: {current_user.username}")
        print(f"=" * 60)
        
        # 1. Get Session and Answers
        print("Step 1: Fetching session...")
        session_result = await db.execute(
            select(QuizSession).where(
                QuizSession.session_id == submit_data.sessionId,
                QuizSession.user_id == current_user.id
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            print(f"ERROR: Session not found for {submit_data.sessionId}")
            raise HTTPException(status_code=404, detail="Session not found")
        print(f"✓ Session found: {session.session_id}")
        
        print("Step 2: Fetching answers...")
        answer_result = await db.execute(
            select(QuizAnswer).where(QuizAnswer.session_id == submit_data.sessionId)
        )
        answer_record = answer_result.scalar_one_or_none()
        
        if not answer_record:
            print(f"ERROR: No answers found for session {submit_data.sessionId}")
            raise HTTPException(status_code=400, detail="No answers found for this session")
        print(f"✓ Answers found")

        # 2. Prepare context for AI
        print("Step 3: Preparing AI context...")
        quiz_context = {
            "scenario": {
                "question": answer_record.scenario_question,
                "answer": answer_record.scenario_answer
            },
            "answers": answer_record.questions_and_answers
        }
        print(f"✓ Context prepared: {quiz_context}")

        # 3. Call AI Service with DB session for RAG
        print("Step 4: Calling AI service...")
        recommendations = await ai_service.generate_recommendations(db, quiz_context)
        print(f"✓ AI recommendations received")

        # 4. Save recommendations to DB
        print("Step 5: Saving to database...")
        rec_model = AIRecommendation(
            session_id=submit_data.sessionId,
            user_id=current_user.id,
            recommendations=recommendations
        )
        db.add(rec_model)
        
        # Mark session as completed
        session.completed = True
        
        await db.commit()
        print(f"✓ Saved to database")
        
        print(f"=" * 60)
        print(f"SUBMIT QUIZ - SUCCESS")
        print(f"=" * 60)
        
        return QuizSubmitResponse(
            success=True,
            message="Recommendations generated",
            status="completed",
            recommendations=recommendations
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"=" * 60)
        print(f"CRITICAL ERROR in submit_quiz:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print(f"=" * 60)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from pathlib import Path
from fastapi.responses import FileResponse

@app.get("/")
async def read_root():
    """API Root - Health Check"""
    return {
        "status": "running",
        "message": "BeauTips API is running",
        "version": "1.0.0",
        "docs": "/api/docs"
    }
