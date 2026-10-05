# StudioRec — веб-приложение «Студия звукозаписи»

Учебный проект (ПР 61–63): реляционная БД и начальная версия веб-приложения для управления
студией звукозаписи — договоры, альбомы и треки, расписание сессий, тиражирование.

**Стек:** Python 3.12 · Flask · Jinja2 · SQLite · HTML/CSS (тёмная тема)

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env  (и задайте свой SECRET_KEY)
python init_db.py               # создаёт studio.db: схема + демо-данные
python app.py                   # http://127.0.0.1:5000
```

## Демо-аккаунты (пароль у всех: `demo1234`)

| Роль | E-mail |
|---|---|
| Администратор | admin@studio.example |
| Продюсер | producer@studio.example |
| Исполнитель | artist@studio.example |
| Звукорежиссёр | engineer@studio.example |

## Структура

```
app.py          маршруты Flask: вход, панель, альбомы, расписание, бронирование
schema.sql      схема БД: 16 таблиц, индексы, 4 триггера бизнес-правил
init_db.py      создание БД и демо-данных
templates/      Jinja2-шаблоны
static/         стили
tests/          проверка правил БД (python -m unittest discover -s tests)
.env.example    пример настроек (реальный .env в репозиторий не попадает)
```

## Секреты

Файлы `.env` и `*.db` добавлены в `.gitignore` — в репозиторий не попадают.
