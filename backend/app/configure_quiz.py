"""Apply the 15-question catalog without changing existing attempt snapshots."""
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Question, QuizConfig
from app.seed import QUIZ_CATALOG

def apply():
    with SessionLocal() as db:
        added = 0
        for item in QUIZ_CATALOG:
            question = db.scalar(select(Question).where(Question.text == item['text']))
            if question is None:
                question = Question(**item)
                db.add(question)
                added += 1
            else:
                for key, value in item.items():
                    setattr(question, key, value)
            question.is_active = True
        config = db.get(QuizConfig, 1)
        if config is None:
            config = QuizConfig(id=1)
            db.add(config)
        config.question_count = 15
        config.title = 'Знаток Арктики'
        db.commit()
        print(f'Quiz configured: 15 questions per new attempt; added {added} catalog questions')

if __name__ == '__main__':
    apply()
