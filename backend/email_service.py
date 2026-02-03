"""
Email Service для отправки писем верификации
Поддержка: Gmail SMTP, SendGrid, или другие
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import secrets
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)


class EmailService:
    """Сервис для отправки email"""
    
    def __init__(self):
        # Настройки из .env
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")  # ваш email
        self.smtp_password = os.getenv("SMTP_PASSWORD")  # пароль приложения
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
        self.from_name = os.getenv("FROM_NAME", "BeauTips")
        
        # Проверка наличия обязательных настроек
        self._validate_config()
    
    def _validate_config(self):
        """Проверяет наличие обязательных настроек SMTP"""
        if not self.smtp_user:
            logger.error("❌ SMTP_USER не установлен в .env файле!")
            logger.error("   Добавьте: SMTP_USER=your-email@gmail.com")
        if not self.smtp_password:
            logger.error("❌ SMTP_PASSWORD не установлен в .env файле!")
            logger.error("   Добавьте: SMTP_PASSWORD=your-app-password")
        
        if self.smtp_user and self.smtp_password:
            logger.info(f"✅ SMTP настроен: {self.smtp_user} @ {self.smtp_host}:{self.smtp_port}")
        else:
            logger.warning("⚠️  SMTP не настроен! Письма не будут отправляться.")
        
    def generate_verification_token(self) -> str:
        """Генерирует уникальный токен верификации"""
        return secrets.token_urlsafe(32)
    
    def get_token_expiry(self, hours: int = 24) -> datetime:
        """Возвращает время истечения токена"""
        from datetime import timezone
        return datetime.now(timezone.utc) + timedelta(hours=hours)
    
    def send_verification_email(self, to_email: str, username: str, verification_token: str) -> bool:
        """
        Отправляет письмо с подтверждением email
        
        Args:
            to_email: Email получателя
            username: Имя пользователя
            verification_token: Токен для верификации
            
        Returns:
            bool: True если письмо отправлено успешно
        """
        # Проверка настроек перед отправкой
        if not self.smtp_user or not self.smtp_password:
            logger.error(f"❌ Не удалось отправить письмо на {to_email}: SMTP не настроен")
            logger.error("   Проверьте настройки в .env файле")
            return False
        
        try:
            logger.info(f"📧 Попытка отправить письмо верификации на {to_email}")
            
            # Формируем ссылку верификации
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            verification_link = f"{base_url}/static/verify-email.html?token={verification_token}"
            logger.debug(f"   Ссылка верификации: {verification_link[:50]}...")
            
            # HTML шаблон письма
            html_content = self._get_verification_template(username, verification_link)
            
            # Создаём письмо
            message = MIMEMultipart("alternative")
            message["Subject"] = "Подтвердите ваш email - BeauTips"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Добавляем HTML часть
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            logger.info(f"   Подключение к SMTP: {self.smtp_host}:{self.smtp_port}")
            
            # Отправляем через SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                logger.debug("   STARTTLS...")
                server.starttls()
                
                logger.debug(f"   Авторизация как: {self.smtp_user}")
                server.login(self.smtp_user, self.smtp_password)
                
                logger.debug(f"   Отправка письма...")
                server.send_message(message)
            
            logger.info(f"✅ Письмо верификации успешно отправлено на {to_email}")
            print(f"✅ Verification email sent to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Ошибка аутентификации SMTP: {str(e)}")
            logger.error("   Проверьте SMTP_USER и SMTP_PASSWORD в .env")
            logger.error("   Для Gmail используйте App Password, а не обычный пароль!")
            print(f"❌ SMTP Authentication Error: {str(e)}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Ошибка SMTP: {str(e)}")
            print(f"❌ SMTP Error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при отправке письма: {str(e)}", exc_info=True)
            print(f"❌ Failed to send email: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_verification_template(self, username: str, verification_link: str) -> str:
        """HTML шаблон письма верификации"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            color: white;
            margin: 0;
            font-size: 28px;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content h2 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .content p {{
            color: #555;
            line-height: 1.6;
            font-size: 16px;
        }}
        .button {{
            display: inline-block;
            padding: 16px 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 30px;
            font-weight: bold;
            margin: 20px 0;
            transition: transform 0.3s;
        }}
        .button:hover {{
            transform: translateY(-2px);
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #777;
            font-size: 14px;
        }}
        .expires {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 20px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✨ BeauTips</h1>
        </div>
        
        <div class="content">
            <h2>Привет, {username}! 👋</h2>
            
            <p>
                Спасибо за регистрацию в <strong>BeauTips</strong> - вашем персональном 
                консультанте по уходу за кожей!
            </p>
            
            <p>
                Чтобы начать получать AI-рекомендации по уходу за кожей, 
                пожалуйста, подтвердите ваш email адрес:
            </p>
            
            <center>
                <a href="{verification_link}" class="button">
                    Подтвердить Email
                </a>
            </center>
            
            <div class="expires">
                <strong>⏰ Важно:</strong> Ссылка действительна в течение 24 часов.
            </div>
            
            <p style="color: #999; font-size: 14px; margin-top: 30px;">
                Если вы не регистрировались на BeauTips, просто проигнорируйте это письмо.
            </p>
        </div>
        
        <div class="footer">
            <p>
                © 2026 BeauTips. Персональный уход за кожей с AI.<br>
                <a href="https://beautips.kg" style="color: #667eea;">beautips.kg</a>
            </p>
        </div>
    </div>
</body>
</html>
        """
    
    def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Отправляет приветственное письмо после верификации"""
        try:
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; }}
        .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 16px; padding: 40px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #667eea; }}
        .button {{ display: inline-block; padding: 16px 40px; background: #667eea; color: white; text-decoration: none; border-radius: 30px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Добро пожаловать в BeauTips!</h1>
        </div>
        
        <p>Привет, {username}!</p>
        
        <p>Ваш email успешно подтверждён! Теперь вы можете:</p>
        
        <ul>
            <li>✨ Получать AI-рекомендации по уходу за кожей</li>
            <li>🔬 Проверять совместимость косметических средств</li>
            <li>📊 Отслеживать историю ваших анализов</li>
            <li>💡 Получать персональные советы</li>
        </ul>
        
        <center>
            <a href="http://localhost:8000/static/chat.html" class="button">
                Начать первый квиз
            </a>
        </center>
        
        <p style="margin-top: 30px; color: #777;">
            Желаем вам здоровой и красивой кожи! 
        </p>
    </div>
</body>
</html>
            """
            
            message = MIMEMultipart("alternative")
            message["Subject"] = "Добро пожаловать в BeauTips! 🎉"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            
            print(f"✅ Welcome email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send welcome email: {str(e)}")
            return False


# Singleton instance
email_service = EmailService()