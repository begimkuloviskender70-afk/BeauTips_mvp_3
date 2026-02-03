"""
Custom Exceptions для BeauTips API
Централизованная обработка ошибок
"""

from typing import Any, Dict, Optional


class BeauTipsException(Exception):
    """Базовый класс для всех исключений приложения"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


# ============ Authentication Errors ============

class AuthenticationError(BeauTipsException):
    """Базовая ошибка аутентификации"""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, error_code="AUTH_ERROR", **kwargs)


class InvalidCredentialsError(AuthenticationError):
    """Неверные учётные данные"""
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, error_code="INVALID_CREDENTIALS")


class TokenExpiredError(AuthenticationError):
    """Токен истёк"""
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, error_code="TOKEN_EXPIRED")


class InvalidTokenError(AuthenticationError):
    """Недействительный токен"""
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, error_code="INVALID_TOKEN")


class UserNotFoundError(BeauTipsException):
    """Пользователь не найден"""
    def __init__(self, message: str = "User not found"):
        super().__init__(message, status_code=404, error_code="USER_NOT_FOUND")


class UserAlreadyExistsError(BeauTipsException):
    """Пользователь уже существует"""
    def __init__(self, field: str = "email", message: str = None):
        msg = message or f"User with this {field} already exists"
        super().__init__(
            msg,
            status_code=400,
            error_code="USER_ALREADY_EXISTS",
            details={"field": field}
        )


class InactiveUserError(AuthenticationError):
    """Пользователь неактивен"""
    def __init__(self, message: str = "User account is inactive"):
        super().__init__(message, error_code="USER_INACTIVE")


# ============ Quiz Errors ============

class QuizError(BeauTipsException):
    """Базовая ошибка квиза"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=400, error_code="QUIZ_ERROR", **kwargs)


class SessionNotFoundError(BeauTipsException):
    """Сессия не найдена"""
    def __init__(self, session_id: str):
        super().__init__(
            f"Quiz session not found",
            status_code=404,
            error_code="SESSION_NOT_FOUND",
            details={"session_id": session_id}
        )


class AnswersNotFoundError(BeauTipsException):
    """Ответы не найдены"""
    def __init__(self, session_id: str):
        super().__init__(
            "No answers found for this session",
            status_code=404,
            error_code="ANSWERS_NOT_FOUND",
            details={"session_id": session_id}
        )


class InvalidQuizDataError(QuizError):
    """Невалидные данные квиза"""
    def __init__(self, message: str = "Invalid quiz data", details: Dict = None):
        super().__init__(message, error_code="INVALID_QUIZ_DATA", details=details)


class QuizAlreadyCompletedError(QuizError):
    """Квиз уже завершён"""
    def __init__(self, session_id: str):
        super().__init__(
            "This quiz session is already completed",
            error_code="QUIZ_ALREADY_COMPLETED",
            details={"session_id": session_id}
        )


# ============ AI Service Errors ============

class AIServiceError(BeauTipsException):
    """Базовая ошибка AI сервиса"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, error_code="AI_SERVICE_ERROR", **kwargs)


class AIGenerationError(AIServiceError):
    """Ошибка генерации рекомендаций"""
    def __init__(self, message: str = "Failed to generate recommendations"):
        super().__init__(message, error_code="AI_GENERATION_FAILED")


class AIAPIError(AIServiceError):
    """Ошибка API провайдера (Gemini)"""
    def __init__(self, message: str = "AI API error", provider: str = "gemini"):
        super().__init__(
            message,
            error_code="AI_API_ERROR",
            details={"provider": provider}
        )


class AIRateLimitError(AIServiceError):
    """Превышен лимит запросов к AI"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            "AI API rate limit exceeded. Please try again later.",
            status_code=429,
            error_code="AI_RATE_LIMIT",
            details={"retry_after_seconds": retry_after}
        )


class ProductsNotFoundError(AIServiceError):
    """Продукты не найдены в RAG"""
    def __init__(self, message: str = "No suitable products found"):
        super().__init__(
            message,
            status_code=404,
            error_code="PRODUCTS_NOT_FOUND"
        )


# ============ Database Errors ============

class DatabaseError(BeauTipsException):
    """Базовая ошибка базы данных"""
    def __init__(self, message: str = "Database operation failed", **kwargs):
        super().__init__(message, status_code=500, error_code="DATABASE_ERROR", **kwargs)


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к БД"""
    def __init__(self, message: str = "Failed to connect to database"):
        super().__init__(message, error_code="DB_CONNECTION_ERROR")


class DatabaseIntegrityError(DatabaseError):
    """Нарушение целостности БД"""
    def __init__(self, message: str = "Database integrity constraint violated"):
        super().__init__(
            message,
            status_code=400,
            error_code="DB_INTEGRITY_ERROR"
        )


# ============ Validation Errors ============

class ValidationError(BeauTipsException):
    """Ошибка валидации данных"""
    def __init__(self, message: str, field: str = None, **kwargs):
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        super().__init__(
            message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details,
            **kwargs
        )


class MissingFieldError(ValidationError):
    """Отсутствует обязательное поле"""
    def __init__(self, field: str):
        super().__init__(
            f"Required field '{field}' is missing",
            field=field,
            error_code="MISSING_FIELD"
        )


class InvalidFormatError(ValidationError):
    """Неверный формат данных"""
    def __init__(self, field: str, expected_format: str):
        super().__init__(
            f"Invalid format for field '{field}'. Expected: {expected_format}",
            field=field,
            error_code="INVALID_FORMAT",
            details={"expected_format": expected_format}
        )


# ============ Permission Errors ============

class PermissionError(BeauTipsException):
    """Недостаточно прав"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message,
            status_code=403,
            error_code="PERMISSION_DENIED"
        )


class ResourceNotOwnedError(PermissionError):
    """Попытка доступа к чужому ресурсу"""
    def __init__(self, resource: str = "resource"):
        super().__init__(
            f"You don't have permission to access this {resource}",
            error_code="RESOURCE_NOT_OWNED"
        )


# ============ Rate Limiting Errors ============

class RateLimitError(BeauTipsException):
    """Превышен лимит запросов"""
    def __init__(self, retry_after: int = 60, limit: str = "requests"):
        super().__init__(
            f"Rate limit exceeded for {limit}. Please try again later.",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after_seconds": retry_after}
        )


# ============ External Service Errors ============

class ExternalServiceError(BeauTipsException):
    """Ошибка внешнего сервиса"""
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            f"{service} service error: {message}",
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service}
        )