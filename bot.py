import os
import logging
import json
import asyncio
from typing import Dict, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from questions_loader import QuestionsLoader
import random

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация загрузчика вопросов
questions_loader = QuestionsLoader()

# Хранилище состояний пользователей
user_states = {}

class UserState:
    def __init__(self):
        self.current_question = None
        self.score = 0
        self.total_questions = 0
        self.awaiting_answer = False
        self.selected_answers = []
        self.mode = None
        self.current_task = None

class HealthHandler(BaseHTTPRequestHandler):
    """Обработчик для health check"""
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Отключаем логирование запросов"""
        pass

def start_health_server():
    """Запуск сервера для health check"""
    try:
        port = int(os.getenv('PORT', 10000))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"Health check server запущен на порту {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Ошибка запуска health check сервера: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user_states[user_id] = UserState()
    
    total_questions = questions_loader.get_questions_count()
    available_tasks = questions_loader.get_available_tasks()
    
    keyboard = [
        [InlineKeyboardButton("📝 Случайное задание", callback_data="random")],
        [InlineKeyboardButton("🎯 Задания по номерам", callback_data="by_task")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 Привет! Я бот для подготовки к ЕГЭ по русскому языку.\n\n"
        f"📚 В базе: {total_questions} заданий\n"
        f"📋 Доступно заданий: {len(available_tasks)} типов\n\n"
        "🔹 Задания из открытого банка ФИПИ\n"
        "🔹 Удобные кнопки для ответов\n"
        "🔹 Подробные объяснения\n\n"
        "Выбери режим работы:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    keyboard = [
        [InlineKeyboardButton("📝 Случайное задание", callback_data="random")],
        [InlineKeyboardButton("🎯 Задания по номерам", callback_data="by_task")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text("Главное меню:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)

async def show_task_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные номера заданий"""
    task_numbers = questions_loader.get_available_tasks()
    
    keyboard = []
    row = []
    for num in task_numbers:
        count = len(questions_loader.get_questions_by_task(num))
        button_text = f"📝 Задание {num} ({count})"
        row.append(InlineKeyboardButton(button_text, callback_data=f"task_{num}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_text(
        "Выбери номер задания для практики:\n"
        "(в скобках указано количество заданий)",
        reply_markup=reply_markup
    )

async def show_question(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                       question_data=None, task_number=None):
    """Показать вопрос пользователю"""
    user_id = update.effective_user.id
    
    if user_id not in user_states:
        user_states[user_id] = UserState()
    
    state = user_states[user_id]
    
    if question_data is None:
        if task_number:
            question = questions_loader.get_random_question(task_number)
            state.mode = 'by_task'
            state.current_task = task_number
        else:
            question = questions_loader.get_random_question()
            state.mode = 'random'
    else:
        question = question_data
    
    if not question:
        await update.callback_query.message.reply_text("❌ Вопросы не найдены.")
        return
    
    state.current_question = question
    state.awaiting_answer = True
    state.selected_answers = []
    state.total_questions += 1
    
    question_text = f"📌 Задание {question['task_number']}\n"
    question_text += f"📊 Сложность: {question.get('difficulty', 'medium').upper()}\n\n"
    question_text += f"❓ {question['question']}\n\n"
    
    if question.get('text'):
        question_text += f"📄 {question['text']}\n\n"
    
    if question.get('options'):
        question_text += "Варианты ответов:\n"
        keyboard = []
        
        for i, option in enumerate(question['options'], 1):
            question_text += f"{i}. {option}\n"
            button_text = option[:50] + ('...' if len(option) > 50 else '')
            keyboard.append([InlineKeyboardButton(
                f"{i}. {button_text}", 
                callback_data=f"answer_{i}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("✅ Проверить", callback_data="check_answer"),
            InlineKeyboardButton("💡 Подсказка", callback_data="hint")
        ])
        keyboard.append([
            InlineKeyboardButton("➡️ Следующий", callback_data="next_question"),
            InlineKeyboardButton("🔙 Меню", callback_data="main_menu")
        ])
    else:
        question_text += "✏️ Введите ваш ответ текстом:"
        keyboard = [
            [InlineKeyboardButton("💡 Показать ответ", callback_data="show_answer")],
            [InlineKeyboardButton("➡️ Следующий", callback_data="next_question")],
            [InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(question_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "random":
        await show_question(update, context)
    elif data == "by_task":
        await show_task_numbers(update, context)
    elif data == "stats":
        await show_stats(update, context)
    elif data == "about":
        await show_about(update, context)
    elif data == "main_menu":
        await show_main_menu(update, context)
    elif data.startswith("task_"):
        task_number = int(data.split("_")[1])
        await show_question(update, context, task_number=task_number)
    elif data.startswith("answer_"):
        await select_answer(update, context, int(data.split("_")[1]))
    elif data == "check_answer":
        await check_answer(update, context)
    elif data == "hint":
        await show_hint(update, context)
    elif data == "show_answer":
        await show_answer(update, context)
    elif data == "next_question":
        state = user_states.get(user_id)
        if state and state.mode == 'by_task' and state.current_task:
            await show_question(update, context, task_number=state.current_task)
        else:
            await show_question(update, context)

async def select_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, answer_num: int):
    """Выбор ответа пользователем"""
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    query = update.callback_query
    
    if not state or not state.current_question:
        return
    
    if answer_num in state.selected_answers:
        state.selected_answers.remove(answer_num)
    else:
        state.selected_answers.append(answer_num)
    
    question = state.current_question
    question_text = f"📌 Задание {question['task_number']}\n\n"
    question_text += f"❓ {question['question']}\n\n"
    
    if question.get('text'):
        question_text += f"📄 {question['text']}\n\n"
    
    if question.get('options'):
        question_text += "Варианты ответов:\n"
        keyboard = []
        
        for i, option in enumerate(question['options'], 1):
            if i in state.selected_answers:
                question_text += f"✅ {i}. {option}\n"
                button_text = f"✅ {i}. {option[:50]}"
            else:
                question_text += f"{i}. {option}\n"
                button_text = f"{i}. {option[:50]}"
            
            keyboard.append([InlineKeyboardButton(
                button_text, 
                callback_data=f"answer_{i}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("✅ Проверить", callback_data="check_answer"),
            InlineKeyboardButton("💡 Подсказка", callback_data="hint")
        ])
        keyboard.append([
            InlineKeyboardButton("➡️ Следующий", callback_data="next_question"),
            InlineKeyboardButton("🔙 Меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(question_text, reply_markup=reply_markup)

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка ответа пользователя"""
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    query = update.callback_query
    
    if not state or not state.current_question:
        await query.message.reply_text("❌ Нет активного вопроса.")
        return
    
    if not state.selected_answers:
        await query.answer("Выберите хотя бы один вариант ответа!", show_alert=True)
        return
    
    question = state.current_question
    correct = question['correct_answer']
    user_answers = sorted(state.selected_answers)
    
    is_correct = False
    if isinstance(correct, list):
        is_correct = sorted(correct) == user_answers
    else:
        is_correct = str(user_answers[0]) == str(correct)
    
    if is_correct:
        state.score += 1
        result_text = "🎉 Отлично! Правильный ответ!"
    else:
        result_text = "❌ Неправильно.\n\n"
        if isinstance(correct, list):
            result_text += f"✅ Правильные ответы: {', '.join(map(str, correct))}\n"
        else:
            result_text += f"✅ Правильный ответ: {correct}\n"
    
    result_text += f"\n📖 Объяснение: {question['explanation']}"
    
    keyboard = [
        [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question")],
        [InlineKeyboardButton("🔙 В меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(result_text, reply_markup=reply_markup)
    state.awaiting_answer = False

async def show_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подсказку"""
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    query = update.callback_query
    
    if not state or not state.current_question:
        return
    
    question = state.current_question
    hint_text = "💡 Подсказка:\n\n"
    
    hints = {
        1: "Обратите внимание на стилистические особенности текста, наличие терминов, эмоциональной лексики.",
        2: "Определите смысловые отношения между частями предложения: причина, следствие, условие, уступка.",
        3: "Обратите внимание на контекст употребления слова и его сочетаемость с другими словами.",
        4: "Вспомните правила постановки ударения в разных частях речи.",
        5: "Вспомните значения паронимов и их сочетаемость с другими словами.",
        6: "Проверьте формы множественного числа существительных и степени сравнения прилагательных.",
        7: "Определите тип грамматической ошибки: согласование, управление, причастный оборот.",
        8: "Вспомните правила чередования гласных в корне: -гар-/-гор-, -зар-/-зор-, -кас-/-кос-.",
        9: "Обратите внимание на правописание приставок пре-/при-.",
        10: "Вспомните правила написания суффиксов причастий.",
        11: "Определите спряжение глагола.",
        12: "Вспомните правила написания НЕ с разными частями речи.",
        13: "Различайте производные предлоги и существительные с предлогами.",
        14: "Вспомните правила написания Н и НН в прилагательных и причастиях.",
        15: "Обратите внимание на однородные члены и обособленные обороты.",
        16: "Найдите причастные и деепричастные обороты.",
        17: "Вводные слова выделяются запятыми.",
        18: "Обращения выделяются запятыми.",
        19: "Определите границы частей сложного предложения.",
        20: "Расставьте знаки между частями сложного предложения."
    }
    
    hint_text += hints.get(question['task_number'], "Внимательно прочитайте вопрос и все варианты ответов.")
    
    await query.answer(hint_text[:200], show_alert=True)

async def show_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать правильный ответ"""
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    query = update.callback_query
    
    if not state or not state.current_question:
        return
    
    question = state.current_question
    correct = question['correct_answer']
    
    if isinstance(correct, list):
        if question['options']:
            correct_text = ", ".join(map(str, correct))
            answer_text = f"✅ Правильные ответы: {correct_text}\n\n"
            for i in correct:
                if i <= len(question['options']):
                    answer_text += f"📌 {i}. {question['options'][i-1]}\n"
        else:
            answer_text = f"✅ Правильный ответ: {correct}"
    else:
        answer_text = f"✅ Правильный ответ: {correct}"
    
    answer_text += f"\n📖 Объяснение: {question['explanation']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(answer_text, reply_markup=reply_markup)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику пользователя"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, UserState())
    query = update.callback_query
    
    stats_text = "📊 Ваша статистика:\n\n"
    stats_text += f"✅ Правильных ответов: {state.score}\n"
    stats_text += f"📝 Всего вопросов: {state.total_questions}\n"
    
    if state.total_questions > 0:
        accuracy = (state.score / state.total_questions) * 100
        stats_text += f"🎯 Точность: {accuracy:.1f}%\n"
    else:
        stats_text += "🎯 Точность: 0%\n"
    
    stats_text += "\n📚 База заданий:\n"
    task_stats = questions_loader.get_statistics()
    for task_num, info in task_stats.items():
        stats_text += f"• Задание {task_num}: {info['count']} шт.\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(stats_text, reply_markup=reply_markup)

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о боте"""
    query = update.callback_query
    
    total_questions = questions_loader.get_questions_count()
    available_tasks = questions_loader.get_available_tasks()
    
    about_text = (
        "ℹ️ О боте\n\n"
        "Этот бот поможет тебе подготовиться к ЕГЭ по русскому языку.\n\n"
        f"📚 В базе: {total_questions} заданий\n"
        f"📋 Типов заданий: {len(available_tasks)}\n\n"
        "🔹 Задания из открытого банка ФИПИ\n"
        "🔹 Удобные кнопки для ответов\n"
        "🔹 Подробные объяснения\n"
        "🔹 Статистика достижений\n\n"
        "Удачи в подготовке! 🍀"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(about_text, reply_markup=reply_markup)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    
    if state and state.awaiting_answer and state.current_question:
        question = state.current_question
        
        if question.get('options') is None:
            user_answer = update.message.text.strip().lower()
            correct_answer = str(question['correct_answer']).strip().lower()
            
            if user_answer == correct_answer:
                state.score += 1
                await update.message.reply_text("🎉 Правильно! Молодец!")
            else:
                await update.message.reply_text(
                    f"❌ Неправильно.\n"
                    f"✅ Правильный ответ: {question['correct_answer']}\n"
                    f"📖 {question['explanation']}"
                )
            
            state.awaiting_answer = False
            keyboard = [
                [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_question")],
                [InlineKeyboardButton("🔙 В меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Продолжим?", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки для ответа.")
    else:
        await start(update, context)

def main():
    """Запуск бота"""
    # Получаем токен из переменных окружения
    token = os.getenv('TELEGRAM_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_TOKEN не установлен!")
        return
    
    # Запускаем health check сервер в отдельном потоке
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Запускаем бота
    logger.info("Бот запущен!")
    
    # Исправление для Python 3.14 - создаем event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        loop.close()

if __name__ == '__main__':
    main()
