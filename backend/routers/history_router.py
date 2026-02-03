"""
Улучшенный History Router с оптимизациями
- Пагинация для больших списков
- Фильтрация и поиск
- Сортировка
- Статистика пользователя
- Кэширование
- Оптимизированные запросы к БД
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Literal
from datetime import datetime, timedelta
import logging
from datetime import timezone
from database import get_db
from models import AIRecommendation, QuizAnswer, QuizSession, User, Product
from auth import get_current_user
from exceptions import SessionNotFoundError, AnswersNotFoundError

router = APIRouter(prefix="/api/history", tags=["History"])
logger = logging.getLogger(__name__)


# ============ Response Models ============

from pydantic import BaseModel, Field

class HistoryItemSummary(BaseModel):
    """Краткая информация о сессии для списка"""
    id: int
    session_id: str
    created_at: str
    scenario: Optional[str] = None
    products_count: int = 0
    analysis_preview: Optional[str] = None
    has_recommendations: bool = False
    
    class Config:
        from_attributes = True


class PaginationInfo(BaseModel):
    """Информация о пагинации"""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class HistoryListResponse(BaseModel):
    """Ответ со списком истории"""
    success: bool = True
    items: List[HistoryItemSummary]
    pagination: PaginationInfo
    stats: dict


class SessionDetailResponse(BaseModel):
    """Детальная информация о сессии"""
    success: bool = True
    session_id: str
    created_at: str
    completed: bool
    quiz_data: dict
    recommendations: Optional[dict]
    related_sessions: List[dict] = []


# ============ Endpoints ============

@router.get("/", response_model=HistoryListResponse)
async def get_user_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    # Пагинация
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(10, ge=1, le=50, description="Элементов на странице"),
    # Сортировка
    sort_by: Literal["date", "scenario"] = Query("date", description="Поле для сортировки"),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Порядок сортировки"),
    # Фильтрация
    scenario_filter: Optional[str] = Query(None, description="Фильтр по сценарию"),
    date_from: Optional[datetime] = Query(None, description="Начальная дата"),
    date_to: Optional[datetime] = Query(None, description="Конечная дата"),
    # Поиск
    search: Optional[str] = Query(None, description="Поиск в анализе"),
):
    """
    Получить историю квизов пользователя с пагинацией и фильтрами
    
    Features:
    - Пагинация (page, page_size)
    - Сортировка (sort_by, sort_order)
    - Фильтрация по дате и сценарию
    - Поиск по тексту
    - Статистика пользователя
    """
    try:
        logger.info(f"Fetching history for user {current_user.id}, page {page}")
        
        # ============ Построение запроса ============
        
        # Базовый запрос с JOIN для оптимизации
        # Используем LEFT JOIN, чтобы получить все рекомендации, даже если нет ответов
        stmt = (
            select(AIRecommendation, QuizAnswer)
            .outerjoin(
                QuizAnswer,
                and_(
                    AIRecommendation.session_id == QuizAnswer.session_id,
                    AIRecommendation.user_id == QuizAnswer.user_id
                )
            )
            .where(AIRecommendation.user_id == current_user.id)
        )
        
        # ============ Фильтры ============
        
        # Фильтр по сценарию
        if scenario_filter:
            stmt = stmt.where(QuizAnswer.scenario_answer.ilike(f"%{scenario_filter}%"))
        
        # Фильтр по датам
        if date_from:
            stmt = stmt.where(AIRecommendation.created_at >= date_from)
        if date_to:
            stmt = stmt.where(AIRecommendation.created_at <= date_to)
        
        # Поиск по тексту (в JSON рекомендаций)
        if search:
            stmt = stmt.where(
                or_(
                    AIRecommendation.recommendations['analysis'].astext.ilike(f"%{search}%"),
                    QuizAnswer.scenario_answer.ilike(f"%{search}%")
                )
            )
        
        # ============ Подсчёт общего количества ============
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total_items = count_result.scalar() or 0
        
        # ============ Сортировка ============
        
        if sort_by == "date":
            order_col = AIRecommendation.created_at
        else:  # scenario
            order_col = QuizAnswer.scenario_answer
        
        if sort_order == "desc":
            stmt = stmt.order_by(desc(order_col))
        else:
            stmt = stmt.order_by(asc(order_col))
        
        # ============ Пагинация ============
        
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # ============ Выполнение запроса ============
        
        result = await db.execute(stmt)
        rows = result.all()
        
        # ============ Формирование ответа ============
        
        items = []
        for rec, quiz in rows:
            recommendations = rec.recommendations or {}
            analysis = recommendations.get('analysis', '')
            products = recommendations.get('products', [])
            
            items.append(HistoryItemSummary(
                id=rec.id,
                session_id=rec.session_id,
                created_at=rec.created_at.isoformat(),
                scenario=quiz.scenario_answer if quiz else None,
                products_count=len(products),
                analysis_preview=analysis[:150] + "..." if len(analysis) > 150 else analysis,
                has_recommendations=bool(products)
            ))
        
        # ============ Пагинация Info ============
        
        total_pages = (total_items + page_size - 1) // page_size
        
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        # ============ Статистика пользователя ============
        
        stats = await get_user_stats(db, current_user.id)
        
        logger.info(f"✅ History fetched: {len(items)} items (page {page}/{total_pages})")
        
        return HistoryListResponse(
            items=items,
            pagination=pagination,
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch history"
        )


@router.get("/stats")
async def get_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить статистику пользователя
    
    Returns:
    - Общее количество квизов
    - Количество завершённых
    - Самый популярный сценарий
    - Средняя частота квизов
    """
    try:
        stats = await get_user_stats(db, current_user.id)
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


async def get_user_stats(db: AsyncSession, user_id: int) -> dict:
    """Вспомогательная функция для получения статистики"""
    
    # Общее количество квизов
    total_stmt = select(func.count(AIRecommendation.id)).where(
        AIRecommendation.user_id == user_id
    )
    total_result = await db.execute(total_stmt)
    total_quizzes = total_result.scalar() or 0
    
    # Количество завершённых сессий
    completed_stmt = (
        select(func.count(QuizSession.id))
        .where(
            QuizSession.user_id == user_id,
            QuizSession.completed == True
        )
    )
    completed_result = await db.execute(completed_stmt)
    completed_quizzes = completed_result.scalar() or 0
    
    # Самый популярный сценарий
    scenario_stmt = (
        select(
            QuizAnswer.scenario_answer,
            func.count(QuizAnswer.id).label('count')
        )
        .where(
            QuizAnswer.user_id == user_id,
            QuizAnswer.scenario_answer.isnot(None)
        )
        .group_by(QuizAnswer.scenario_answer)
        .order_by(desc('count'))
        .limit(1)
    )
    scenario_result = await db.execute(scenario_stmt)
    popular_scenario = scenario_result.first()
    
    # Дата первого квиза
    first_stmt = (
        select(AIRecommendation.created_at)
        .where(AIRecommendation.user_id == user_id)
        .order_by(asc(AIRecommendation.created_at))
        .limit(1)
    )
    first_result = await db.execute(first_stmt)
    first_quiz = first_result.scalar()
    
    # Средняя частота (дней между квизами)
    avg_frequency = None
    if first_quiz and total_quizzes > 1:
        days_since_first = (datetime.now(timezone.utc) - first_quiz).days
        if days_since_first > 0:
            avg_frequency = days_since_first / total_quizzes
    
    return {
        "total_quizzes": total_quizzes,
        "completed_quizzes": completed_quizzes,
        "most_popular_scenario": popular_scenario[0] if popular_scenario else None,
        "avg_frequency_days": round(avg_frequency, 1) if avg_frequency else None,
        "member_since": first_quiz.isoformat() if first_quiz else None
    }


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_details(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_related: bool = Query(False, description="Включить похожие сессии"),
    recommendation_id: Optional[int] = Query(None, description="ID конкретной рекомендации (если не указан, берётся самая новая)")
):
    """
    Получить детальную информацию о конкретной сессии
    
    Features:
    - Полные данные квиза
    - AI рекомендации
    - Опционально: похожие сессии
    """
    try:
        logger.info(f"Getting details for session: {session_id}")
        
        # ============ Получаем данные сессии ============
        
        # Рекомендации
        # Если указан recommendation_id - берём конкретную рекомендацию
        # Иначе берём самую новую
        if recommendation_id:
            rec_stmt = (
                select(AIRecommendation)
                .where(
                    AIRecommendation.id == recommendation_id,
                    AIRecommendation.session_id == session_id,
                    AIRecommendation.user_id == current_user.id
                )
            )
            rec_result = await db.execute(rec_stmt)
            recommendation = rec_result.scalar_one_or_none()
        else:
            # Берем самую новую запись (по created_at)
            rec_stmt = (
                select(AIRecommendation)
                .where(
                    AIRecommendation.session_id == session_id,
                    AIRecommendation.user_id == current_user.id
                )
                .order_by(desc(AIRecommendation.created_at))
                .limit(1)
            )
            rec_result = await db.execute(rec_stmt)
            recommendation_row = rec_result.first()
            recommendation = recommendation_row[0] if recommendation_row else None
        
        # Если нет рекомендации, проверяем, есть ли вообще сессия
        if not recommendation:
            # Проверяем, существует ли сессия
            session_check = (
                select(QuizSession)
                .where(
                    QuizSession.session_id == session_id,
                    QuizSession.user_id == current_user.id
                )
            )
            session_check_result = await db.execute(session_check)
            session_exists = session_check_result.scalar_one_or_none()
            
            if not session_exists:
                raise SessionNotFoundError(session_id)
            
            # Сессия есть, но рекомендаций ещё нет - возвращаем пустые рекомендации
            logger.info(f"Session {session_id} exists but no recommendations yet")
            return SessionDetailResponse(
                session_id=session_id,
                created_at=session_exists.created_at.isoformat() if session_exists else datetime.now(timezone.utc).isoformat(),
                completed=session_exists.completed if session_exists else False,
                quiz_data={
                    "scenario": {"question": None, "answer": None},
                    "answers": []
                },
                recommendations=None,
                related_sessions=[]
            )
        
        # Ответы квиза
        # Используем first() вместо scalar_one_or_none(), так как могут быть дубликаты
        quiz_stmt = (
            select(QuizAnswer)
            .where(
                QuizAnswer.session_id == session_id,
                QuizAnswer.user_id == current_user.id
            )
            .order_by(desc(QuizAnswer.created_at))
            .limit(1)
        )
        quiz_result = await db.execute(quiz_stmt)
        quiz_row = quiz_result.first()
        quiz_answer = quiz_row[0] if quiz_row else None
        
        # Информация о сессии
        # Используем first() вместо scalar_one_or_none(), так как могут быть дубликаты
        session_stmt = (
            select(QuizSession)
            .where(QuizSession.session_id == session_id)
            .order_by(desc(QuizSession.created_at))
            .limit(1)
        )
        session_result = await db.execute(session_stmt)
        session_row = session_result.first()
        session = session_row[0] if session_row else None
        
        # ============ Похожие сессии (если запрошено) ============
        
        related_sessions = []
        if include_related and quiz_answer:
            related_sessions = await find_related_sessions(
                db, 
                current_user.id, 
                session_id,
                quiz_answer.scenario_answer
            )
        
        # ============ Формирование ответа ============
        
        logger.info(f"✅ Session details fetched for {session_id}")
        
        return SessionDetailResponse(
            session_id=session_id,
            created_at=recommendation.created_at.isoformat(),
            completed=session.completed if session else True,
            quiz_data={
                "scenario": {
                    "question": quiz_answer.scenario_question if quiz_answer else None,
                    "answer": quiz_answer.scenario_answer if quiz_answer else None
                },
                "answers": quiz_answer.questions_and_answers if quiz_answer else []
            },
            recommendations=recommendation.recommendations if recommendation.recommendations else None,
            related_sessions=related_sessions
        )
        
    except SessionNotFoundError as e:
        # Правильно обрабатываем 404 ошибку
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    except HTTPException:
        # Пробрасываем HTTP исключения как есть
        raise
    except Exception as e:
        logger.error(f"Error getting session details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session details: {str(e)}"
        )


async def find_related_sessions(
    db: AsyncSession, 
    user_id: int, 
    exclude_session_id: str,
    scenario: Optional[str]
) -> List[dict]:
    """Найти похожие сессии пользователя"""
    
    stmt = (
        select(AIRecommendation, QuizAnswer)
        .join(
            QuizAnswer,
            AIRecommendation.session_id == QuizAnswer.session_id
        )
        .where(
            AIRecommendation.user_id == user_id,
            AIRecommendation.session_id != exclude_session_id
        )
    )
    
    # Фильтр по похожему сценарию
    if scenario:
        stmt = stmt.where(QuizAnswer.scenario_answer == scenario)
    
    stmt = stmt.order_by(desc(AIRecommendation.created_at)).limit(3)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    related = []
    for rec, quiz in rows:
        related.append({
            "session_id": rec.session_id,
            "created_at": rec.created_at.isoformat(),
            "scenario": quiz.scenario_answer,
            "products_count": len(rec.recommendations.get('products', []))
        })
    
    return related


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить сессию квиза
    
    Note: Удаление каскадное - удалятся все связанные записи
    """
    try:
        logger.info(f"Deleting session: {session_id} for user {current_user.id}")
        
        # Проверяем существование
        stmt = select(QuizSession).where(
            QuizSession.session_id == session_id,
            QuizSession.user_id == current_user.id
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise SessionNotFoundError(session_id)
        
        # Удаляем (каскадно удалятся QuizAnswer и AIRecommendation)
        await db.delete(session)
        await db.commit()
        
        logger.info(f"✅ Session {session_id} deleted")
        
        return {
            "success": True,
            "message": "Session deleted successfully"
        }
        
    except SessionNotFoundError:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete session"
        )


@router.get("/export/csv")
async def export_history_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Экспортировать историю в CSV
    
    Returns: CSV файл со всей историей пользователя
    """
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    try:
        logger.info(f"Exporting history to CSV for user {current_user.id}")
        
        # Получаем все данные
        stmt = (
            select(AIRecommendation, QuizAnswer)
            .join(
                QuizAnswer,
                AIRecommendation.session_id == QuizAnswer.session_id,
                isouter=True
            )
            .where(AIRecommendation.user_id == current_user.id)
            .order_by(desc(AIRecommendation.created_at))
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        # Создаём CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовки
        writer.writerow([
            'Дата',
            'Сценарий',
            'Количество продуктов',
            'Анализ (краткий)',
            'Session ID'
        ])
        
        # Данные
        for rec, quiz in rows:
            recommendations = rec.recommendations or {}
            analysis = recommendations.get('analysis', '')
            products = recommendations.get('products', [])
            
            writer.writerow([
                rec.created_at.strftime('%Y-%m-%d %H:%M'),
                quiz.scenario_answer if quiz else '',
                len(products),
                analysis[:100] + '...' if len(analysis) > 100 else analysis,
                rec.session_id
            ])
        
        # Возвращаем файл
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM для Excel
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=beautips_history_{datetime.now().strftime('%Y%m%d')}.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to export history"
        )