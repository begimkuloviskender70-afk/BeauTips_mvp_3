"""
Обновлённые модели с поддержкой верификации email
Добавьте эти поля в User модель
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)  # Опционально для будущего
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # ============ НОВОЕ: Верификация Email ============
    email_verified = Column(Boolean, default=False)  # Email подтверждён?
    verification_token = Column(String(255), nullable=True)  # Токен верификации
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)  # Срок действия
    
    # Relationships
    quiz_sessions = relationship("QuizSession", back_populates="user", cascade="all, delete-orphan")
    quiz_answers = relationship("QuizAnswer", back_populates="user", cascade="all, delete-orphan")
    ai_recommendations = relationship("AIRecommendation", back_populates="user", cascade="all, delete-orphan")


# Остальные модели без изменений...
class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="quiz_sessions")
    quiz_answers = relationship("QuizAnswer", back_populates="session", cascade="all, delete-orphan")
    ai_recommendations = relationship("AIRecommendation", back_populates="session", cascade="all, delete-orphan")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("quiz_sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scenario_question = Column(Text)
    scenario_answer = Column(Text)
    questions_and_answers = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="quiz_answers")
    session = relationship("QuizSession", back_populates="quiz_answers")


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("quiz_sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recommendations = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="ai_recommendations")
    session = relationship("QuizSession", back_populates="ai_recommendations")


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(500), nullable=False)
    product_type = Column(String(255))
    brand = Column(String(255))
    country = Column(String(255))
    product_kind = Column(String(255))
    volume = Column(String(100))
    skin_for = Column(Text)
    functions = Column(Text)
    description_1 = Column(Text)
    description_2 = Column(Text)
    components = Column(Text)
    ingredients_list = Column(Text)
    price_min = Column(Integer)
    price_max = Column(Integer)
    
    reviews = relationship("Review", back_populates="product")


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    review_text = Column(Text)
    
    product = relationship("Product", back_populates="reviews")