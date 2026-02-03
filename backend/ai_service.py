import os
import json
import asyncio
import re
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select, and_, or_, not_
from sqlalchemy.orm import selectinload
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# We need access to database models
from models import Product, Review

load_dotenv()


class PromptTemplates:
    """Динамические промпты для разных сценариев"""
    
    SKIN_CARE = """
    Ты дерматокосметолог. Проанализируй:
    - Тип кожи: {skin_type}
    - Проблемы: {conditions}
    - Бюджет: {budget}
    
    ⚠️ КРИТИЧЕСКИ ВАЖНО: Бюджет пользователя - {budget}. 
    ТЫ ДОЛЖЕН ВЫБРАТЬ ТОЛЬКО ПРОДУКТЫ, ЦЕНА КОТОРЫХ НЕ ПРЕВЫШАЕТ УКАЗАННЫЙ БЮДЖЕТ!
    Если в списке есть продукты с ценой выше бюджета - НЕ ИСПОЛЬЗУЙ ИХ!
    Если все продукты превышают бюджет - сообщи об этом в analysis и предложи альтернативы.
    
    Составь routine из {products_count} продуктов для:
    - Решения проблем: {main_concerns}
    - Долгосрочного результата
    - СТРОГО В РАМКАХ БЮДЖЕТА {budget}
    
    Объясни ПОЧЕМУ каждый продукт подходит.
    
    ДОСТУПНЫЕ ТОВАРЫ ИЗ НАШЕЙ БАЗЫ (RAG):
    {relevant_products}
    
    ДАННЫЕ ПОЛЬЗОВАТЕЛЯ (КВИЗ):
    {user_context}
    
    ИНСТРУКЦИИ:
    1. Проанализируй данные пользователя.
    2. Из предоставленного списка продуктов ВЫБЕРИ ТОЛЬКО те, которые:
       - Лучше всего подходят этому пользователю
       - НЕ ПРЕВЫШАЮТ бюджет {budget} (проверь цену каждого продукта!)
    3. Составь четкий план: утренняя и вечерняя рутина с указанием НАЗВАНИЙ продуктов из списка.
    4. Выдели ключевые ингредиенты.
    5. Дай советы по образу жизни.
    6. В analysis укажи, что все рекомендованные продукты соответствуют бюджету {budget}.
    
    ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON:
    {{
        "analysis": "... (обязательно упомяни, что все продукты в рамках бюджета {budget})",
        "key_ingredients": ["...", "..."],
        "products": [
            {{
                "name": "Название продукта",
                "brand": "Бренд (если есть)",
                "reason": "Почему подходит этому пользователю (кратко)"
            }},
            ...
        ],
        "routine": {{
            "morning": ["Шаг 1: [Название продукта] - описание...", "Шаг 2: ..."],
            "evening": ["Шаг 1: [Название продукта] - описание...", "Шаг 2: ..."]
        }},
        "lifestyle_tips": ["...", "..."],
        "disclaimer": "..."
    }}
    """
    
    PRODUCT_COMPATIBILITY = """
    Ты химик-косметолог. Проанализируй совместимость:
    Продукты: {products}
    
    Проверь:
    1. Конфликтующие активы (ретинол + AHA, витамин C + ниацинамид)
    2. pH совместимость
    3. Порядок нанесения
    4. Риски раздражения
    
    Дай рекомендации по правильному сочетанию.
    
    ДОСТУПНЫЕ ТОВАРЫ ИЗ НАШЕЙ БАЗЫ (RAG):
    {relevant_products}
    
    ДАННЫЕ ПОЛЬЗОВАТЕЛЯ (КВИЗ):
    {user_context}
    
    ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON:
    {{
        "analysis": "...",
        "compatibility_check": {{
            "conflicts": ["...", "..."],
            "safe_combinations": ["...", "..."],
            "application_order": ["...", "..."]
        }},
        "recommendations": ["...", "..."],
        "disclaimer": "..."
    }}
    """
    
    ROUTINE_ANALYSIS = """
    Ты аналитик рутин. У пользователя есть:
    {current_products}
    
    Оцени:
    1. Что работает хорошо
    2. Чего не хватает (пробелы)
    3. Что можно заменить на более эффективное
    4. Оптимальный порядок использования
    
    Предложи улучшения из базы продуктов.
    
    ДОСТУПНЫЕ ТОВАРЫ ИЗ НАШЕЙ БАЗЫ (RAG):
    {relevant_products}
    
    ДАННЫЕ ПОЛЬЗОВАТЕЛЯ (КВИЗ):
    {user_context}
    
    ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON:
    {{
        "analysis": "...",
        "current_routine_assessment": {{
            "working_well": ["...", "..."],
            "missing": ["...", "..."],
            "improvements": ["...", "..."]
        }},
        "recommended_products": [
            {{
                "name": "Название продукта",
                "brand": "Бренд",
                "reason": "Почему рекомендуется"
            }}
        ],
        "optimal_order": ["...", "..."],
        "disclaimer": "..."
    }}
    """
    
    DEFAULT = """
    Вы — ведущий эксперт BeauTips, профессиональный врач-дерматокосметолог.
    Ваша цель: составить идеальный план ухода, используя доступные в нашей базе продукты.
    
    ДОСТУПНЫЕ ТОВАРЫ ИЗ НАШЕЙ БАЗЫ (RAG):
    {relevant_products}
    
    ДАННЫЕ ПОЛЬЗОВАТЕЛЯ (КВИЗ):
    {user_context}
    
    ИНСТРУКЦИИ:
    1. Проанализируй данные пользователя.
    2. Из предоставленного списка продуктов ВЫБЕРИ те, которые лучше всего подходят этому пользователю.
    3. Составь четкий план: утренняя и вечерняя рутина с указанием НАЗВАНИЙ продуктов из списка.
    4. Выдели ключевые ингредиенты.
    5. Дай советы по образу жизни.
    
    ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON:
    {{
        "analysis": "...",
        "key_ingredients": ["...", "..."],
        "products": [
            {{
                "name": "Название продукта",
                "brand": "Бренд (если есть)",
                "reason": "Почему подходит этому пользователю (кратко)"
            }},
            ...
        ],
        "routine": {{
            "morning": ["Шаг 1: [Название продукта] - описание...", "Шаг 2: ..."],
            "evening": ["Шаг 1: [Название продукта] - описание...", "Шаг 2: ..."]
        }},
        "lifestyle_tips": ["...", "..."],
        "disclaimer": "..."
    }}
    """


def extract_user_profile(user_data: dict) -> dict:
    """
    Извлекает профиль пользователя из данных квиза
    """
    profile = {
        'skin_type': None,
        'conditions': [],
        'budget': None,
        'allergens': [],
        'age': None,
        'scenario': user_data.get("scenario", {}).get("answer", "")
    }
    
    # Сначала проверяем scenarioData для бюджета (новый формат)
    scenario_data = user_data.get("scenarioData", {})
    if isinstance(scenario_data, dict):
        skin_care_data = scenario_data.get("skin-care", {})
        if isinstance(skin_care_data, dict):
            budget_from_data = skin_care_data.get("budget")
            if budget_from_data:
                try:
                    if isinstance(budget_from_data, str):
                        if budget_from_data.lower() in ['any', 'любой', 'не важно']:
                            profile['budget'] = 'any'
                        else:
                            # Извлекаем число из строки
                            numbers = re.findall(r'\d+', budget_from_data)
                            if numbers:
                                profile['budget'] = int(numbers[0])
                    elif isinstance(budget_from_data, (int, float)):
                        profile['budget'] = int(budget_from_data)
                except (ValueError, TypeError):
                    pass
    
    answers = user_data.get("answers", [])
    if not isinstance(answers, list):
        answers = []
    
    # Поиск информации в ответах
    for qa in answers:
        if not isinstance(qa, dict):
            continue
            
        question = qa.get("question", "").lower()
        answer = qa.get("answer", "")
        
        if not answer:
            continue
        
        # Тип кожи
        if any(keyword in question for keyword in ["тип кожи", "тип", "кожа", "обычно ведёт"]):
            profile['skin_type'] = answer
        
        # Проблемы/условия
        if any(keyword in question for keyword in ["проблем", "состояние", "concern", "проблема", "беспокоит"]):
            if isinstance(answer, list):
                profile['conditions'].extend(answer)
            else:
                profile['conditions'].append(answer)
        
        # Бюджет (если еще не извлечен из scenarioData)
        if not profile.get('budget'):
            if any(keyword in question for keyword in ["бюджет", "budget", "цена", "стоимость"]):
                # Пытаемся извлечь число из ответа
                if isinstance(answer, str):
                    # Ищем числа в строке
                    numbers = re.findall(r'\d+', answer)
                    if numbers:
                        profile['budget'] = int(numbers[0])
                    elif answer.lower() in ['any', 'любой', 'не важно', 'бюджет не важен']:
                        profile['budget'] = 'any'
                elif isinstance(answer, (int, float)):
                    profile['budget'] = int(answer)
        
        # Аллергены
        if any(keyword in question for keyword in ["аллерг", "allerg", "неперенос", "избегать", "компонент"]):
            if isinstance(answer, list):
                profile['allergens'].extend(answer)
            else:
                profile['allergens'].append(answer)
        
        # Возраст
        if any(keyword in question for keyword in ["возраст", "age"]):
            profile['age'] = answer
    
    return profile


def calculate_product_score(product: Product, user_profile: dict) -> dict:
    """
    Расчет score для каждого продукта с объяснением
    """
    score = 0
    reasons = []
    
    # 1. Тип кожи (30 points)
    skin_type = user_profile.get('skin_type')
    if skin_type and product.skin_for:
        skin_type_lower = skin_type.lower()
        skin_for_lower = product.skin_for.lower()
        if skin_type_lower in skin_for_lower or skin_for_lower in skin_type_lower:
            score += 30
            reasons.append(f"Подходит для {skin_type} кожи")
    
    # 2. Проблемы кожи (40 points)
    concerns = user_profile.get('conditions', [])
    matching_functions = []
    if concerns and product.functions:
        functions_lower = product.functions.lower()
        for concern in concerns:
            if isinstance(concern, str) and concern.lower() in functions_lower:
                score += 10
                matching_functions.append(concern)
    
    if matching_functions:
        reasons.append(f"Решает проблемы: {', '.join(matching_functions)}")
    
    # 3. Отзывы (20 points)
    if product.reviews:
        positive_keywords = ['хорош', 'отлично', 'рекоменд', 'нравится', 'эффектив', 'помог']
        negative_keywords = ['плох', 'не понравил', 'не рекоменд', 'не подош']
        
        positive_count = 0
        negative_count = 0
        
        for review in product.reviews:
            review_text_lower = review.review_text.lower() if review.review_text else ""
            if any(keyword in review_text_lower for keyword in positive_keywords):
                positive_count += 1
            elif any(keyword in review_text_lower for keyword in negative_keywords):
                negative_count += 1
        
        if positive_count > 0:
            review_score = min(20, positive_count * 5)
            score += review_score
            reasons.append(f"{positive_count} положительных отзывов")
    
    # 4. Бюджет (10 points)
    budget = user_profile.get('budget')
    if budget and budget != 'any' and product.price_max:
        try:
            budget_int = int(budget) if isinstance(budget, str) else budget
            if product.price_max <= budget_int:
                score += 10
                reasons.append("В рамках бюджета")
        except (ValueError, TypeError):
            pass
    
    return {
        'product': product,
        'score': score,
        'reasons': reasons
    }


def get_prompt_for_scenario(scenario: str, user_data: dict, relevant_products: str) -> str:
    """
    Получает промпт для конкретного сценария
    """
    user_context = json.dumps(user_data, ensure_ascii=False)
    profile = extract_user_profile(user_data)
    
    scenario_lower = scenario.lower() if scenario else ""
    
    # Определяем тип сценария
    if "совместим" in scenario_lower or "compatibility" in scenario_lower:
        template_name = "PRODUCT_COMPATIBILITY"
        template = PromptTemplates.PRODUCT_COMPATIBILITY
        return template.format(
            products=profile.get('conditions', []),
            relevant_products=relevant_products,
            user_context=user_context
        )
    elif "рутин" in scenario_lower or "routine" in scenario_lower or "анализ" in scenario_lower:
        template_name = "ROUTINE_ANALYSIS"
        template = PromptTemplates.ROUTINE_ANALYSIS
        return template.format(
            current_products=profile.get('conditions', []),
            relevant_products=relevant_products,
            user_context=user_context
        )
    elif "улучш" in scenario_lower or "уход" in scenario_lower or "кожа" in scenario_lower:
        template_name = "SKIN_CARE"
        template = PromptTemplates.SKIN_CARE
        return template.format(
            skin_type=profile.get('skin_type', 'не указан'),
            conditions=', '.join(profile.get('conditions', [])) if profile.get('conditions') else 'не указаны',
            budget=profile.get('budget', 'не указан'),
            main_concerns=', '.join(profile.get('conditions', [])) if profile.get('conditions') else 'не указаны',
            products_count=5,
            relevant_products=relevant_products,
            user_context=user_context
        )
    else:
        # Дефолтный промпт
        template = PromptTemplates.DEFAULT
        return template.format(
            relevant_products=relevant_products,
            user_context=user_context
        )


class AIService:
    def __init__(self):
        self.model_name = "gemini-2.5-flash"
        self.embedding_model = None
        self.knowledge_base = []
        self.knowledge_embeddings = None
        self._is_indexed = False
        self._client = None

    def _get_client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                self._client = genai.Client(api_key=api_key)
        return self._client

    def _ensure_embeddings(self, db_products=None):
        if self.embedding_model is None:
            # Using a small, fast multilingual model
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        if db_products:
            self.knowledge_base = []
            texts = []
            for p in db_products:
                # Collect reviews
                reviews_text = " ".join([r.review_text for r in p.reviews]) if p.reviews else "Нет отзывов."
                
                content = f"Бренд: {p.brand}. Тип: {p.product_type}. Назначение: {p.skin_for}. Функции: {p.functions}. Состав: {p.ingredients_list}. ОТЗЫВЫ ПОЛЬЗОВАТЕЛЕЙ: {reviews_text}"
                self.knowledge_base.append({
                    "id": p.id,
                    "name": p.product_name,
                    "content": content
                })
                texts.append(f"{p.product_name}: {content}")
            
            if texts:
                self.knowledge_embeddings = self.embedding_model.encode(texts)
                self._is_indexed = True

    async def _fetch_filtered_products(self, db, user_profile: dict) -> List[Product]:
        """
        Получает продукты с фильтрацией по бюджету, аллергенам и типу кожи
        """
        stmt = select(Product).options(selectinload(Product.reviews))
        conditions = []
        
        # Фильтрация по бюджету
        budget = user_profile.get('budget')
        if budget and budget != 'any':
            try:
                max_price = int(budget) if isinstance(budget, str) else budget
                conditions.append(Product.price_max <= max_price)
            except (ValueError, TypeError):
                pass
        
        # Фильтрация по аллергенам
        allergens = user_profile.get('allergens', [])
        if allergens:
            allergen_conditions = []
            for allergen in allergens:
                if isinstance(allergen, str) and allergen.strip():
                    # Исключаем продукты, содержащие этот аллерген
                    allergen_conditions.append(~Product.ingredients_list.ilike(f'%{allergen.strip()}%'))
            # Продукт должен НЕ содержать НИ ОДНОГО аллергена (AND для всех исключений)
            if allergen_conditions:
                conditions.extend(allergen_conditions)
        
        # Фильтрация по типу кожи
        skin_type = user_profile.get('skin_type')
        if skin_type and isinstance(skin_type, str):
            conditions.append(Product.skin_for.ilike(f'%{skin_type}%'))
        
        # Применяем условия
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def _get_enriched_context(self, db, user_profile: dict, user_query: str, top_k: int = 10) -> str:
        """
        Обогащенный контекст с скорингом и статистикой
        Комбинирует векторный поиск с фильтрацией
        """
        # Шаг 1: Убеждаемся, что индекс создан
        if not self._is_indexed:
            stmt = select(Product).options(selectinload(Product.reviews))
            result = await db.execute(stmt)
            products = result.scalars().all()
            self._ensure_embeddings(products)
        
        if self.knowledge_embeddings is None or not self.knowledge_base:
            return "Информация о продуктах в базе данных отсутствует."
        
        # Шаг 2: Векторный поиск - получаем релевантные продукты по запросу
        user_emb = self.embedding_model.encode([user_query])
        similarities = cosine_similarity(user_emb, self.knowledge_embeddings)[0]
        
        # Получаем больше продуктов для фильтрации (top_k * 3)
        top_indices = similarities.argsort()[-(top_k * 3):][::-1]
        
        # Шаг 3: Получаем продукты из БД по ID из векторного поиска
        product_ids = [self.knowledge_base[i]['id'] for i in top_indices]
        
        # Если нет ID, возвращаем сообщение
        if not product_ids:
            return "Продукты в базе данных не найдены."
        
        stmt = select(Product).where(Product.id.in_(product_ids)).options(selectinload(Product.reviews))
        result = await db.execute(stmt)
        vector_products = result.scalars().all()
        
        # Если продукты не найдены в БД, возвращаем сообщение
        if not vector_products:
            return "Продукты не найдены в базе данных."
        
        # Создаем словарь для быстрого доступа
        products_by_id = {p.id: p for p in vector_products}
        similarity_by_id = {self.knowledge_base[i]['id']: similarities[i] for i in top_indices}
        
        # Шаг 4: СТРОГАЯ фильтрация по бюджету и аллергенам
        budget = user_profile.get('budget')
        budget_int = None
        if budget and budget != 'any':
            try:
                budget_int = int(budget) if isinstance(budget, str) else budget
            except (ValueError, TypeError):
                pass
        
        # Сначала фильтруем продукты строго по бюджету и аллергенам
        filtered_products = []
        for product_id in product_ids:
            if product_id not in products_by_id:
                continue
            product = products_by_id[product_id]
            
            # СТРОГАЯ проверка бюджета - исключаем продукты, превышающие бюджет
            if budget_int is not None and product.price_max:
                if product.price_max > budget_int:
                    continue  # Пропускаем продукт, если превышает бюджет
            
            # СТРОГАЯ проверка аллергенов - исключаем продукты с аллергенами
            allergens = user_profile.get('allergens', [])
            if allergens and product.ingredients_list:
                has_allergen = False
                for allergen in allergens:
                    if isinstance(allergen, str) and allergen.strip():
                        if allergen.strip().lower() in product.ingredients_list.lower():
                            has_allergen = True
                            break
                if has_allergen:
                    continue  # Пропускаем продукт с аллергеном
            
            filtered_products.append(product_id)
        
        # Если после строгой фильтрации осталось мало продуктов, расширяем поиск
        if len(filtered_products) < 3:
            # Пробуем найти продукты в рамках бюджета из всего списка
            all_products_stmt = select(Product).options(selectinload(Product.reviews))
            if budget_int is not None:
                all_products_stmt = all_products_stmt.where(Product.price_max <= budget_int)
            result = await db.execute(all_products_stmt)
            additional_products = result.scalars().all()
            
            # Добавляем дополнительные продукты, которые соответствуют бюджету
            for product in additional_products:
                if product.id not in filtered_products:
                    # Проверяем аллергены
                    allergens = user_profile.get('allergens', [])
                    if allergens and product.ingredients_list:
                        has_allergen = False
                        for allergen in allergens:
                            if isinstance(allergen, str) and allergen.strip():
                                if allergen.strip().lower() in product.ingredients_list.lower():
                                    has_allergen = True
                                    break
                        if has_allergen:
                            continue
                    filtered_products.append(product.id)
                    products_by_id[product.id] = product
        
        # Шаг 5: Применяем скоринг к отфильтрованным продуктам
        scored_products = []
        for product_id in filtered_products:
            if product_id not in products_by_id:
                continue
            product = products_by_id[product_id]
            
            # Базовый score из векторного поиска (0-1, нормализуем до 50 баллов)
            similarity_score = similarity_by_id.get(product_id, 0) * 50
            
            # Применяем фильтры как бонус
            filter_bonus = 0
            
            # Бюджет - бонус за соответствие (все уже отфильтрованы)
            if budget_int is not None and product.price_max:
                if product.price_max <= budget_int:
                    filter_bonus += 10  # Бонус за соответствие бюджету
            
            # Тип кожи - бонус если подходит
            skin_type = user_profile.get('skin_type')
            if skin_type and product.skin_for:
                if skin_type.lower() in product.skin_for.lower():
                    filter_bonus += 10
            
            # Итоговый score (без штрафов, так как уже отфильтровали)
            final_score = similarity_score + filter_bonus
            
            # Используем функцию calculate_product_score для дополнительных баллов
            product_score_data = calculate_product_score(product, user_profile)
            final_score += product_score_data['score']
            
            scored_products.append({
                'product': product,
                'score': final_score,
                'reasons': product_score_data['reasons'],
                'similarity': similarity_by_id.get(product_id, 0)
            })
        
        # Сортировка по итоговому score
        scored_products.sort(key=lambda x: x['score'], reverse=True)
        top_products = scored_products[:top_k]
        
        # Если после фильтров осталось мало продуктов, ищем больше в рамках бюджета
        if len(top_products) < 3 and budget_int is not None:
            # Ищем дополнительные продукты строго в рамках бюджета
            additional_stmt = select(Product).where(Product.price_max <= budget_int).options(selectinload(Product.reviews))
            result = await db.execute(additional_stmt)
            additional_products = result.scalars().all()
            
            # Фильтруем по аллергенам
            allergens = user_profile.get('allergens', [])
            for product in additional_products:
                if product.id in [p['product'].id for p in top_products]:
                    continue  # Уже в списке
                
                # Проверяем аллергены
                if allergens and product.ingredients_list:
                    has_allergen = False
                    for allergen in allergens:
                        if isinstance(allergen, str) and allergen.strip():
                            if allergen.strip().lower() in product.ingredients_list.lower():
                                has_allergen = True
                                break
                    if has_allergen:
                        continue
                
                # Добавляем продукт
                product_score_data = calculate_product_score(product, user_profile)
                similarity_score = 30  # Базовый score для дополнительных продуктов
                final_score = similarity_score + product_score_data['score']
                
                top_products.append({
                    'product': product,
                    'score': final_score,
                    'reasons': product_score_data['reasons'],
                    'similarity': 0.3
                })
            
            # Пересортировываем
            top_products.sort(key=lambda x: x['score'], reverse=True)
            top_products = top_products[:top_k]
        
        # Проверка: если все еще нет продуктов, возвращаем сообщение
        if not top_products:
            return "Подходящие продукты не найдены. Попробуйте изменить параметры поиска или фильтрации."
        
        # Формирование контекста
        context_parts = []
        for idx, item in enumerate(top_products):
            p = item['product']
            
            # Статистика отзывов
            positive_keywords = ['хорош', 'отлично', 'рекоменд', 'нравится', 'эффектив', 'помог']
            negative_keywords = ['плох', 'не понравил', 'не рекоменд', 'не подош']
            
            positive_count = 0
            negative_count = 0
            
            if p.reviews:
                for review in p.reviews:
                    review_text_lower = review.review_text.lower() if review.review_text else ""
                    if any(keyword in review_text_lower for keyword in positive_keywords):
                        positive_count += 1
                    elif any(keyword in review_text_lower for keyword in negative_keywords):
                        negative_count += 1
            
            reviews_stats = {
                'positive': positive_count,
                'negative': negative_count,
                'total': len(p.reviews) if p.reviews else 0
            }
            
            # Топ отзыв
            top_review = "Нет отзывов"
            if p.reviews and p.reviews[0].review_text:
                top_review = p.reviews[0].review_text[:100] + "..."
            
            # Формируем список причин
            reasons_text = chr(10).join(f"✓ {r}" for r in item['reasons']) if item['reasons'] else "✓ Базовое соответствие"
            
            context = f"""
ПРОДУКТ #{idx+1} [Релевантность: {item['score']:.1f}/100]
Название: {p.product_name}
Бренд: {p.brand or 'Не указан'}
Тип: {p.product_type or 'Не указан'}
Цена: {p.price_min or 0}-{p.price_max or 0} сом

Для кожи: {p.skin_for or 'Не указано'}
Функции: {p.functions or 'Не указано'}
Ключевые компоненты: {p.components or 'Не указано'}

ПОЧЕМУ ПОДХОДИТ:
{reasons_text}

ОТЗЫВЫ: {reviews_stats['positive']}+ / {reviews_stats['negative']}- (всего: {reviews_stats['total']})
Топ отзыв: "{top_review}"
"""
            context_parts.append(context)
        
        return "\n\n" + "="*80 + "\n\n".join(context_parts)
    
    async def _get_relevant_context(self, db, user_query: str, user_profile: dict = None, top_k: int = 10) -> str:
        """
        Получает релевантный контекст с использованием фильтрации и обогащения
        """
        if user_profile is None:
            user_profile = {}
        
        # Если индекс еще не создан, создаем его
        if not self._is_indexed:
            stmt = select(Product).options(selectinload(Product.reviews))
            result = await db.execute(stmt)
            products = result.scalars().all()
            self._ensure_embeddings(products)
        
        # Используем обогащенный контекст
        return await self._get_enriched_context(db, user_profile, user_query, top_k)

    async def generate_recommendations(self, db, user_data: dict) -> dict:
        """
        Generates skincare recommendations using RAG and Gemini 2.5 Flash.
        Now uses filtered products, scoring, and dynamic prompts.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {
                "error": "GOOGLE_API_KEY not configured",
                "analysis": "ИИ-консультант ожидает настройки ключа доступа.",
                "disclaimer": "Обратитесь к администратору для настройки Gemini API."
            }

        try:
            # 1. Extract user profile
            user_profile = extract_user_profile(user_data)
            
            # 2. Prepare search query
            scenario_ans = user_data.get("scenario", {}).get("answer", "")
            quiz_ans = str(user_data.get("answers", []))
            search_query = f"{scenario_ans} {quiz_ans}"
            
            # 3. RAG: Retrieve relevant products with filtering and enrichment
            relevant_products = await self._get_relevant_context(
                db, 
                search_query, 
                user_profile=user_profile,
                top_k=10
            )

            # 4. Get scenario for dynamic prompt
            scenario = scenario_ans or user_profile.get('scenario', '')
            
            # 5. Construct dynamic prompt
            prompt = get_prompt_for_scenario(scenario, user_data, relevant_products)

            # 6. Generate with Gemini (NEW API)
            client = self._get_client()
            if not client:
                return {
                    "error": "Failed to initialize Gemini client",
                    "analysis": "Не удалось подключиться к ИИ Gemini.",
                    "disclaimer": "Проверьте настройки API ключа."
                }

            # Run synchronous API call in executor
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
            )

            # 7. Parse JSON
            text_response = response.text
            if "```json" in text_response:
                text_response = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                text_response = text_response.split("```")[1].split("```")[0].strip()
            
            recommendations = json.loads(text_response)
            
            # 8. Валидация: проверяем, что все рекомендованные продукты соответствуют бюджету
            budget_int = None
            if user_profile.get('budget') and user_profile.get('budget') != 'any':
                try:
                    budget_int = int(user_profile.get('budget')) if isinstance(user_profile.get('budget'), str) else user_profile.get('budget')
                except (ValueError, TypeError):
                    pass
            
            if budget_int is not None and recommendations.get('products'):
                # Проверяем каждый продукт в базе данных
                product_names = [p.get('name', '') for p in recommendations.get('products', [])]
                if product_names:
                    stmt = select(Product).where(Product.product_name.in_(product_names))
                    result = await db.execute(stmt)
                    db_products = {p.product_name: p for p in result.scalars().all()}
                    
                    # Фильтруем продукты, превышающие бюджет
                    valid_products = []
                    for product in recommendations.get('products', []):
                        product_name = product.get('name', '')
                        db_product = db_products.get(product_name)
                        
                        if db_product and db_product.price_max:
                            if db_product.price_max <= budget_int:
                                valid_products.append(product)
                            else:
                                print(f"⚠️ Продукт {product_name} превышает бюджет: {db_product.price_max} > {budget_int}")
                        else:
                            # Если продукт не найден в БД, оставляем его (может быть общее название)
                            valid_products.append(product)
                    
                    # Обновляем список продуктов
                    recommendations['products'] = valid_products
                    
                    # Обновляем analysis, если продукты были отфильтрованы
                    if len(valid_products) < len(recommendations.get('products', [])):
                        original_analysis = recommendations.get('analysis', '')
                        recommendations['analysis'] = f"{original_analysis}\n\nВсе рекомендованные продукты соответствуют указанному бюджету до {budget_int} сом."
            
            return recommendations

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")
            print(f"Response text: {response.text[:500] if 'response' in locals() else 'N/A'}")
            return {
                "error": "JSON parsing error",
                "analysis": "ИИ вернул ответ в неожиданном формате.",
                "disclaimer": "Пожалуйста, попробуйте отправить результаты еще раз."
            }
        except Exception as e:
            print(f"CRITICAL ERROR in Gemini AI Service: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "analysis": "Произошла техническая заминка при работе с ИИ Gemini.",
                "disclaimer": "Пожалуйста, попробуйте отправить результаты еще раз через минуту."
            }


ai_service = AIService()