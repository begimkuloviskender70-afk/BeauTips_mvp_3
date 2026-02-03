"""
Обновлённый Auth Router с верификацией Email
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta, datetime, timezone
import logging

from database import get_db
from models import User
from schemas import UserCreate, UserLogin, UserResponse, Token, ResendVerificationRequest
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from email_service import email_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя с отправкой письма верификации
    """
    try:
        logger.info(f"Registration attempt for email: {user_data.email}")
        
        # Проверка существующего email
        email_result = await db.execute(
            select(User).where(User.email == user_data.email.lower())
        )
        if email_result.scalar_one_or_none():
            logger.warning(f"Registration failed - email exists: {user_data.email}")
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        
        # Проверка существующего username
        username_result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if username_result.scalar_one_or_none():
            logger.warning(f"Registration failed - username exists: {user_data.username}")
            raise HTTPException(
                status_code=400,
                detail="User with this username already exists"
            )
        
        # Создаём пользователя
        hashed_password = get_password_hash(user_data.password)
        
        # Генерируем токен верификации
        verification_token = email_service.generate_verification_token()
        token_expires = email_service.get_token_expiry(hours=24)
        
        new_user = User(
            email=user_data.email.lower(),
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=True,
            email_verified=False,  # НЕ подтверждён
            verification_token=verification_token,
            verification_token_expires=token_expires
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # Отправляем письмо в фоне (не блокируем ответ)
        background_tasks.add_task(
            email_service.send_verification_email,
            new_user.email,
            new_user.username,
            verification_token
        )
        
        logger.info(f"✅ User registered: {new_user.username} (ID: {new_user.id})")
        logger.info(f"📧 Verification email scheduled for: {new_user.email}")
        
        return UserResponse(
            id=new_user.id,
            email=new_user.email,
            username=new_user.username,
            phone=new_user.phone,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
            email_verified=new_user.email_verified
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )


@router.post("/verify-email")
async def verify_email(
    token: str = Query(..., description="Verification token from email"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """
    Подтверждение email по токену
    Принимает token как query параметр: /api/auth/verify-email?token=...
    """
    try:
        logger.info(f"Email verification attempt with token: {token[:10]}...")
        
        # Ищем пользователя с этим токеном
        result = await db.execute(
            select(User).where(User.verification_token == token)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("Verification failed - invalid token")
            raise HTTPException(
                status_code=400,
                detail="Invalid verification token"
            )
        
        # Проверяем срок действия токена
        now = datetime.now(timezone.utc)
        if user.verification_token_expires < now:
            logger.warning(f"Verification failed - token expired for user {user.email}")
            raise HTTPException(
                status_code=400,
                detail="Verification token has expired. Please request a new one."
            )
        
        # Подтверждаем email
        user.email_verified = True
        user.verification_token = None  # Удаляем использованный токен
        user.verification_token_expires = None
        
        await db.commit()
        
        # Отправляем приветственное письмо
        background_tasks.add_task(
            email_service.send_welcome_email,
            user.email,
            user.username
        )
        
        logger.info(f"✅ Email verified for user: {user.username}")
        
        return {
            "success": True,
            "message": "Email verified successfully! You can now login.",
            "username": user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Email verification failed"
        )


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """
    Повторная отправка письма верификации
    """
    try:
        email = request.email.lower()
        logger.info(f"Resend verification request for: {email}")
        
        # Ищем пользователя
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Не раскрываем существование email
            logger.warning(f"Resend failed - user not found: {email}")
            return {
                "success": True,
                "message": "If an account exists, verification email has been sent."
            }
        
        if user.email_verified:
            logger.info(f"Email already verified: {email}")
            raise HTTPException(
                status_code=400,
                detail="Email is already verified"
            )
        
        # Генерируем новый токен
        verification_token = email_service.generate_verification_token()
        token_expires = email_service.get_token_expiry(hours=24)
        
        user.verification_token = verification_token
        user.verification_token_expires = token_expires
        
        await db.commit()
        
        # Отправляем письмо
        background_tasks.add_task(
            email_service.send_verification_email,
            user.email,
            user.username,
            verification_token
        )
        
        logger.info(f"✅ Verification email resent to: {email}")
        
        return {
            "success": True,
            "message": "Verification email has been resent. Please check your inbox."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Resend verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to resend verification email"
        )


@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Вход пользователя (требует подтверждённый email)
    """
    try:
        logger.info(f"Login attempt for email: {user_credentials.email}")
        
        # Находим пользователя
        result = await db.execute(
            select(User).where(User.email == user_credentials.email.lower())
        )
        user = result.scalar_one_or_none()
        
        # Проверяем credentials
        if not user or not verify_password(user_credentials.password, user.hashed_password):
            logger.warning(f"Login failed - invalid credentials: {user_credentials.email}")
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # НОВОЕ: Проверяем верификацию email
        if not user.email_verified:
            logger.warning(f"Login failed - email not verified: {user_credentials.email}")
            raise HTTPException(
                status_code=403,
                detail="Please verify your email before logging in. Check your inbox."
            )
        
        # Проверяем активность
        if not user.is_active:
            logger.warning(f"Login failed - inactive user: {user_credentials.email}")
            raise HTTPException(
                status_code=403,
                detail="User account is inactive"
            )
        
        # Создаём токен
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        logger.info(f"✅ Login successful: {user.username} (ID: {user.id})")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                email=user.email,
                username=user.username,
                phone=user.phone,
                is_active=user.is_active,
                created_at=user.created_at,
                email_verified=user.email_verified
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Login failed due to server error"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о текущем пользователе"""
    logger.info(f"User info requested: {current_user.username}")
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        phone=current_user.phone,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        email_verified=current_user.email_verified
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Выход (client-side удаление токена)"""
    logger.info(f"User logged out: {current_user.username}")
    
    return {
        "success": True,
        "message": "Logged out successfully"
    }