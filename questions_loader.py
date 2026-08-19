import json
import os
import logging
from typing import List, Dict, Any
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuestionsLoader:
    """Загрузчик вопросов из папки data"""
    
    def __init__(self):
        self.data_dir = "data"
        self.tasks_dir = os.path.join(self.data_dir, "tasks")
        self.all_questions_file = os.path.join(self.data_dir, "all_questions.json")
        self.questions = []
        self.load_all_questions()
    
    def load_all_questions(self):
        """Загрузка всех вопросов из файла"""
        self.questions = []
        
        # Проверяем наличие файла с вопросами
        if os.path.exists(self.all_questions_file):
            try:
                with open(self.all_questions_file, 'r', encoding='utf-8') as f:
                    self.questions = json.load(f)
                logger.info(f"✅ Загружено {len(self.questions)} вопросов из all_questions.json")
                return
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки all_questions.json: {e}")
        
        # Загружаем из отдельных файлов в папке tasks
        if os.path.exists(self.tasks_dir):
            for filename in os.listdir(self.tasks_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.tasks_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            task_questions = json.load(f)
                            self.questions.extend(task_questions)
                            logger.info(f"📄 Загружено {len(task_questions)} вопросов из {filename}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка загрузки {filename}: {e}")
        
        # Если вопросы не найдены, создаем примеры
        if not self.questions:
            logger.warning("⚠️ Вопросы не найдены, создаю 5 примеров...")
            self.create_sample_questions()
        
        logger.info(f"📚 Всего загружено {len(self.questions)} вопросов")
    
    def create_sample_questions(self):
        """Создание примеров вопросов (только если нет файла)"""
        self.questions = [
            {
                "id": "sample_1",
                "task_number": 1,
                "type": "multiple_choice",
                "question": "Укажите варианты ответов, в которых даны верные характеристики фрагмента текста.",
                "text": "«Научный стиль характеризуется точностью, логичностью.»",
                "options": [
                    "В тексте используется разговорная лексика",
                    "Текст относится к научному стилю",
                    "В тексте присутствуют термины",
                    "Текст имеет художественный характер"
                ],
                "correct_answer": [2, 3],
                "explanation": "Текст относится к научному стилю.",
                "difficulty": "easy"
            },
            {
                "id": "sample_2",
                "task_number": 2,
                "type": "text_input",
                "question": "Самостоятельно подберите подчинительный союз.",
                "text": "Он не пришёл на встречу, ... был очень занят.",
                "options": None,
                "correct_answer": "потому что",
                "explanation": "Союз 'потому что' указывает на причину.",
                "difficulty": "easy"
            },
            {
                "id": "sample_3",
                "task_number": 4,
                "type": "multiple_choice",
                "question": "В одном из слов допущена ошибка в постановке ударения.",
                "text": "Выберите слово с ошибкой.",
                "options": [
                    "звонИт",
                    "тОрты",
                    "красИвее",
                    "бАловать"
                ],
                "correct_answer": [4],
                "explanation": "Правильно: баловАть.",
                "difficulty": "medium"
            },
            {
                "id": "sample_4",
                "task_number": 6,
                "type": "multiple_choice",
                "question": "В одном из слов допущена ошибка в образовании формы слова.",
                "text": "Исправьте ошибку.",
                "options": [
                    "пара сапогов",
                    "более умный",
                    "с тремястами рублями",
                    "лягте на пол"
                ],
                "correct_answer": [1],
                "explanation": "Правильно: пара сапог.",
                "difficulty": "easy"
            },
            {
                "id": "sample_5",
                "task_number": 8,
                "type": "multiple_choice",
                "question": "Укажите варианты ответов с чередующейся гласной корня.",
                "text": "Выберите правильный вариант.",
                "options": [
                    "з..ря, к..саться, р..сти",
                    "г..реть, з..рница, к..снуться",
                    "р..сток, отр..сль, пол..жение",
                    "все варианты верны"
                ],
                "correct_answer": [4],
                "explanation": "Во всех рядах чередующиеся гласные.",
                "difficulty": "medium"
            }
        ]
        
        # Сохраняем примеры
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.all_questions_file, 'w', encoding='utf-8') as f:
            json.dump(self.questions, f, ensure_ascii=False, indent=2)
        logger.info(f"Создано {len(self.questions)} примеров вопросов")
    
    def get_all_questions(self):
        """Получить все вопросы"""
        return self.questions
    
    def get_questions_by_task(self, task_number: int):
        """Получить вопросы по номеру задания"""
        return [q for q in self.questions if q['task_number'] == task_number]
    
    def get_random_question(self, task_number: int = None):
        """Получить случайный вопрос"""
        if task_number:
            questions = self.get_questions_by_task(task_number)
        else:
            questions = self.questions
        
        return random.choice(questions) if questions else None
    
    def get_available_tasks(self):
        """Получить список доступных заданий"""
        task_numbers = set()
        for q in self.questions:
            task_numbers.add(q['task_number'])
        return sorted(task_numbers)
    
    def get_statistics(self):
        """Получить статистику по вопросам"""
        stats = {}
        for q in self.questions:
            task_num = q['task_number']
            if task_num not in stats:
                stats[task_num] = {'count': 0}
            stats[task_num]['count'] += 1
        return stats
    
    def get_questions_count(self):
        """Получить общее количество вопросов"""
        return len(self.questions)
    
    def reload(self):
        """Перезагрузить вопросы"""
        self.load_all_questions()
