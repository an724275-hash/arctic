# Подключение фронтенда

Базовый адрес разработки: `http://localhost:8000/api/v1`. Интерактивные запросы и полные модели доступны в `http://localhost:8000/docs`. Машиночитаемый контракт — `/openapi.json`.

## Авторизация

`POST /auth/login` принимает JSON:

```json
{"email":"participant@example.com","password":"DemoPass123!"}
```

Ответ содержит `access_token`, `refresh_token`, `expires_in`, `token_type` и `user`. Пароль выше используется только в подготовленной локальной демонстрации; при `seed --demo` на другом сервере вы задаёте собственный пароль.

Передавайте `Authorization: Bearer <access_token>` в закрытые запросы. `POST /auth/refresh` принимает `{"refresh_token":"..."}` и возвращает новую пару. Старый refresh нельзя повторять: повторное использование отзывает сессии. На фронте обновляйте токен одним запросом, не запускайте несколько refresh одновременно.

Не кладите токены в URL. Предпочтительно держать access token в памяти; политику хранения refresh определяет выбранная архитектура фронтенда. Swagger Authorize использует `/auth/token`: в поле username вводится почта.

## Порядок подключения экранов

| Экран | Запросы |
| --- | --- |
| Главная | `GET /content?kind=news`, `GET /public/stats`, `GET /stages` |
| Образовательные материалы | `GET /content?kind=education`, `GET /content/{slug}` |
| FAQ с поиском | `GET /content?kind=faq&q=сертификат` |
| Профиль | `GET/PATCH /users/me` |
| Тест | `GET /quiz/config`, `POST /quiz/attempts`, `GET /quiz/attempts/{id}` |
| Награды | `GET /certificates`, скачивание по `download_url` с Bearer |
| Мои проекты | `GET/POST /projects`, `GET /nominations` |
| Эксперт | `GET /expert/assignments`, `GET /criteria` |
| Педагог | `GET /teachers/students` |
| Защиты | `GET /defenses` |
| Администратор | `GET /admin/stats`, `GET /admin/users`, `GET /projects` |
| Уведомления | `GET /notifications?unread_only=true` |

Контракты: [аккаунты и администрация](AUTH_API.md), [тесты и сертификаты](QUIZ_API.md), [проекты и экспертиза](PROJECT_API.md).

## Общие правила

- Идентификаторы — UUID-строки. Даты — ISO 8601 с часовым поясом; серверные соединения PostgreSQL используют UTC. На экране переводите дату в часовой пояс пользователя.
- JSON: `Content-Type: application/json`. При отправке `FormData` не выставляйте Content-Type вручную — браузер добавит multipart boundary.
- Файлы закрыты авторизацией. Скачивайте через `fetch` с Bearer, затем создавайте URL из `Blob`; прямой `<a href>` не добавит заголовок авторизации.
- Списки поддерживают `limit` и `offset`, если они указаны в Swagger. Большинство списков — массивы; административные пользователи, обращения, очередь и журнал — `{items,total,limit,offset}`.
- Ошибка бизнес-правила: `{"detail":"Сообщение"}`. Ошибка входных данных: `detail` — массив объектов с `loc`, `msg`, `type`.
- `401`: нет действующей сессии; `403`: нет прав; `404`: запись не найдена; `409`: состояние запрещает действие; `413`: большой файл; `422`: неправильные данные; `429`: повторите позднее.
- Контент `body` хранится как текст. Не вставляйте его в DOM через небезопасный HTML. Если нужен Markdown/HTML, используйте проверенный renderer и очистку HTML на фронте.
- Публичные счётчики читают реальные записи базы; для обновления на главной достаточно периодического GET. WebSocket-счётчика нет.

## Пример запроса

```ts
const response = await fetch(`${apiUrl}/projects`, {
  headers: { Authorization: `Bearer ${accessToken}` },
});
if (!response.ok) throw await response.json();
const projects = await response.json();
```

В локальной базе подготовлены роли `participant`, `teacher`, `expert`, `admin`, `commission`; также есть второй участник и эксперт для проверки доступа. Email совпадает с ролью: `participant@example.com`, `expert2@example.com`. Публичная регистрация создаёт только участника или педагога; эксперт и администратор создаются через админку или CLI.

## Границы демонстрации

Порог теста, количество попыток, вопросы, номинации и критерии изменяются через админский API. Исходные seed-значения демонстрационные. Доступ к подаче проектов пока не зависит от успешного теста: Положение с правилами допуска не было приложено к ТЗ, их нужно уточнить.

Фронтенд должен предоставить страницы `/verify-email?token=...`, `/reset-password?token=...`, `/teacher/confirm?token=...`: они получают токен из письма и отправляют его в соответствующий POST API. Ссылки не подтверждаются простым GET, чтобы почтовые сканеры не расходовали токены.
