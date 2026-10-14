import argparse
import getpass
import os
from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Content, Criterion, Nomination, Question, QuizConfig, Stage, User, utcnow
from app.security import hash_password


import json
from pathlib import Path

QUIZ_CATALOG = json.loads(Path(__file__).with_name('quiz_catalog.json').read_text(encoding='utf-8'))
QUESTIONS = [(q['text'], [o['text'] for o in q['options']], int(q['correct_option_ids'][0])) for q in QUIZ_CATALOG]



def seed_catalog(db):
    if not db.get(QuizConfig, 1):
        db.add(QuizConfig(id=1, question_count=15, duration_seconds=600, pass_percent=60, max_attempts=3))
    for title in ("Исследование Арктики", "Сохраним белого медведя", "Творческий проект"):
        if not db.scalar(select(Nomination).where(Nomination.title == title)):
            db.add(
                Nomination(
                    title=title, description="Демонстрационная номинация. Заменить по Положению конкурса."
                )
            )
    for name, weight in (("Актуальность", 1), ("Обоснованность", 2), ("Качество представления", 1)):
        if not db.scalar(select(Criterion).where(Criterion.name == name)):
            db.add(Criterion(name=name, max_score=10, weight=weight, description="Демонстрационный критерий"))
    for position, (slug, title) in enumerate(
        (
            ("registration", "Регистрация"),
            ("testing", "Тестирование"),
            ("projects", "Приём проектов"),
            ("defense", "Защита проектов"),
        )
    ):
        if not db.scalar(select(Stage).where(Stage.slug == slug)):
            db.add(Stage(slug=slug, title=title, position=position))
    for text, options, correct in QUESTIONS:
        if not db.scalar(select(Question).where(Question.text == text)):
            db.add(
                Question(
                    text=text,
                    options=[{"id": str(i), "text": t} for i, t in enumerate(options)],
                    correct_option_ids=[str(correct)],
                    topic="Арктика",
                    difficulty="easy",
                    explanation=next(q["explanation"] for q in QUIZ_CATALOG if q["text"] == text),
                )
            )
    items = [
        (
            "about",
            "Удивительная и неизведанная Арктика",
            "page",
            "Образовательная платформа школьного конкурса. Изучайте Арктику, проходите тестирование и представляйте свой проект.",
        ),
        (
            "how-to-participate",
            "Как участвовать",
            "page",
            "Зарегистрируйтесь, заполните профиль, пройдите тест и отправьте проект. После проверки работа поступит экспертам.",
        ),
        (
            "demo-materials",
            "Демонстрационная версия",
            "news",
            "Вопросы, номинации и критерии в этой версии приведены для демонстрации. Официальные правила и сроки будут опубликованы организаторами.",
        ),
        (
            "what-is-arctic",
            "Что такое Арктика",
            "education",
            "Арктика — северная полярная область Земли. Её изучение объединяет географию, биологию и климатологию.",
        ),
        (
            "polar-bear",
            "Белый медведь",
            "education",
            "Белый медведь связан с морским льдом, где он охотится на тюленей. Наблюдать за дикими животными следует с безопасного расстояния.",
        ),
        (
            "protect-arctic",
            "Как помочь Арктике",
            "education",
            "Изучайте природу, проверяйте источники, сокращайте количество отходов и рассказывайте о результатах своего исследования.",
        ),
        (
            "faq-certificate",
            "Где скачать сертификат",
            "faq",
            "После завершения теста сертификат появится в личном кабинете. В нём указано участие или успешное прохождение тестирования.",
        ),
    ]
    for slug, title, kind, body in items:
        if not db.scalar(select(Content).where(Content.slug == slug)):
            db.add(
                Content(
                    slug=slug,
                    title=title,
                    kind=kind,
                    body=body,
                    excerpt=body[:180],
                    published=True,
                    extra={"demo": True},
                )
            )
    db.flush()


def seed_demo(db, password: str):
    seed_catalog(db)
    users = {}
    hashed = hash_password(password)
    for key, name in (
        ("participant", "Демо Участник"),
        ("participant2", "Второй Участник"),
        ("teacher", "Демо Педагог"),
        ("expert", "Демо Эксперт"),
        ("expert2", "Второй Эксперт"),
        ("admin", "Демо Администратор"),
        ("commission", "Демо Комиссия"),
    ):
        role = key.rstrip("2")
        email = f"{key}@example.com"
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                full_name=name,
                role=role,
                hashed_password=hashed,
                birth_date=date(2010, 5, 15) if role == "participant" else date(1990, 1, 1),
                school="Демонстрационная школа",
                grade=9 if role == "participant" else None,
                region="Республика Саха (Якутия)",
                consent_at=utcnow(),
                guardian_name="Демо Представитель" if role == "participant" else None,
                guardian_email="guardian@example.com" if role == "participant" else None,
                guardian_consent_at=utcnow() if role == "participant" else None,
                email_verified=True,
            )
            db.add(user)
        users[key] = user
    db.flush()
    return users


def main():
    parser = argparse.ArgumentParser(description="Настройка каталога и создание администратора")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--admin-email")
    args = parser.parse_args()
    with SessionLocal() as db:
        seed_catalog(db)
        if args.demo:
            password = os.getenv("DEMO_PASSWORD") or getpass.getpass(
                "Пароль демонстрационных пользователей: "
            )
            if len(password) < 10:
                raise SystemExit("Нужен пароль не короче 10 символов")
            seed_demo(db, password)
        if args.admin_email:
            email = args.admin_email.strip().lower()
            if db.scalar(select(User.id).where(User.email == email)):
                raise SystemExit("Пользователь уже существует; его роль не изменена")
            password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Пароль администратора: ")
            from app.auth_schemas import validate_password

            validate_password(password)
            db.add(
                User(
                    email=email,
                    full_name="Администратор",
                    role="admin",
                    hashed_password=hash_password(password),
                    email_verified=True,
                    consent_at=utcnow(),
                )
            )
        db.commit()
    print("Начальные данные подготовлены. Демонстрационные материалы помечены demo=true.")


if __name__ == "__main__":
    main()
