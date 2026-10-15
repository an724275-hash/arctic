from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
target = root / '.runtime/public-repo'
target.mkdir(parents=True, exist_ok=True)
directories = ['frontend/src', 'frontend/scripts', 'frontend/tests', 'frontend/public', 'backend/app', 'backend/alembic', 'backend/tests', '.github']
files = ['tools/qa/roles-e2e.cjs', 'tools/qa/create_roles_fixture.py', 'tools/qa/ROLES-E2E.md', 'tools/build_city_directory.py', 'frontend/index.html', 'frontend/vite.config.js', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/.env.example', 'backend/requirements.txt', 'backend/requirements.in', 'backend/pyproject.toml', 'backend/alembic.ini', 'backend/Dockerfile', 'backend/.dockerignore', 'backend/.env.example', 'backend/API.md', 'backend/AUTH_API.md', 'backend/PROJECT_API.md', 'backend/QUIZ_API.md', 'compose.yaml', '.env.example', '.gitignore']
files += [str(p.relative_to(root)).replace('\\','/') for p in (root / 'deploy').iterdir() if p.is_file() and p.name != 'status.json']
for name in directories:
    shutil.copytree(root / name, target / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for name in files:
    dest = target / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / name, dest)
(target / 'README.md').write_text('''# Арктика · asa team

Сайт конкурса «Удивительная и неизведанная Арктика».

Работающий сайт: https://95.85.251.67/

## Стек

JavaScript, Vite, HTML/CSS; Python 3.14, FastAPI, SQLAlchemy, Alembic, PostgreSQL 17; nginx и Docker Compose. PDF-сертификаты: ReportLab и QR-коды.

## Возможности

Регистрация и вход по почте, роли участника, наставника, эксперта, организатора и комиссии; тест из 15 вопросов с серверным таймером и разбором; PDF-сертификаты; сохранение черновиков, отправка и модерация проектов; назначения экспертов и взвешенные оценки; публикация результатов. Семь образовательных тем, анимированный маскот и музыка по нажатию.

VK ID пока не подключён. Доставка писем требует настройки SMTP. Утверждённое положение, сроки и условия награждения публикует организатор.

## Локальный запуск

```sh
cp .env.example .env
# Укажите собственные POSTGRES_PASSWORD и JWT_SECRET.
docker compose up -d --build
cd frontend
npm ci
npm run dev
```

Проверьте VITE_API_BASE_URL и адрес API в frontend/.env.example. Полное развёртывание сайта описано в deploy/README.md.

## Проверка изменений

```sh
npm --prefix frontend run check
npm --prefix frontend run build
cd backend
python -m pytest tests -q
```

Для тестов нужна отдельная PostgreSQL-база arctic_test и TEST_DATABASE_URL. GitHub Actions запускает проверку JS, сборку и тесты с PostgreSQL при push и pull request. Результат конкретной версии виден в Actions рядом с SHA коммита.

## Ассеты

Маскоты предоставлены командой; вариант с флагом Саха подготовлен в Blender. Northern Light — оригинальная синтезированная музыка, условия CC0 в frontend/public/assets/AUDIO-LICENSE.txt. GigaChat подключается только через backend; ключ задаётся в серверном .env. Помощник в закреплённом окне чата требует входа и согласия, блокируется во время теста и ограничен квотой. Обращения участников, партнёров и волонтёров сохраняются в кабинете организатора. Шрифт Noto Sans — OFL. Иллюстрации ландшафта созданы с помощью генерации изображений.

Проект дорабатывался с помощью ИИ и проверялся командой; не заявляется как разработанный без ИИ. Код открыт для ревью. Отдельная лицензия на весь исходный код пока не выбрана.
''', encoding='utf-8')
print('Prepared', len(list(target.rglob('*'))), 'entries')
