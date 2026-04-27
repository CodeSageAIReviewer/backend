# CodeSage AI Reviewer Backend

Backend-сервис для AI Code Review: авторизация пользователей, workspace-логика, интеграции с Git-хостингами, LLM-интеграции и запуск ревью merge request через Celery.

## Содержание
- [1. Что внутри](#1-что-внутри)
- [2. Как устроен runtime-пайплайн](#2-как-устроен-runtime-пайплайн)
- [3. Требования](#3-требования)
- [4. Переменные окружения](#4-переменные-окружения)
- [5. Быстрый запуск через Docker Compose](#5-быстрый-запуск-через-docker-compose)
- [6. Локальный запуск без Docker](#6-локальный-запуск-без-docker)
- [7. Интеграции и особенности](#7-интеграции-и-особенности)
- [8. Структура проекта](#8-структура-проекта)
- [9. Частые проблемы](#9-частые-проблемы)
- [10. Команды-шпаргалка](#10-команды-шпаргалка)

## 1. Что внутри
- `Django 5.2` + `Django REST Framework`
- JWT-аутентификация через `djangorestframework-simplejwt`
- `PostgreSQL` как основная БД
- `Celery + Redis` для фоновых задач:
  - синхронизация merge requests;
  - запуск AI-ревью и публикация комментариев
- LLM-провайдеры: `OpenAI`, `DeepSeek`, `Ollama`
- Git-провайдеры: `GitHub` (рабочая реализация), `GitLab` (заглушка в текущем коде)

## 2. Как устроен runtime-пайплайн

Актуально по текущему коду и `docker-compose.yml`:

1. Клиент обращается к API (`/api/...`) и получает JWT (`/api/users/login/` или `/api/users/register/`).
2. Пользователь создаёт workspace, подключает Git-интеграцию и LLM-интеграцию.
3. При запуске ревью вызывается endpoint:
   - `POST /api/workspace/{workspace_id}/merge-requests/{mr_id}/reviews/run/`
4. API создаёт `ReviewRun` и ставит задачу `run_mr_review` в Celery.
5. Celery worker:
   - подтягивает diff из Git-провайдера;
   - вызывает LLM;
   - парсит ответ;
   - сохраняет комментарии в БД;
   - при `publish=true` публикует комментарий обратно в PR/MR.

Docker Compose поднимает 5 сервисов:
- `db` (PostgreSQL 15)
- `web` (Django dev server на `0.0.0.0:8000`)
- `redis` (broker/result backend)
- `worker` (Celery worker)
- `beat` (Celery beat)

## 3. Требования

### Для Docker-сценария
- Docker
- Docker Compose

### Для локального запуска
- Python `3.12+`
- PostgreSQL `15+` (или совместимая версия)
- Redis `7+` (для Celery)

## 4. Переменные окружения

Создайте `.env` на основе `.env.dist`:

```bash
cp .env.dist .env
```

| Переменная | Обязательна | Пример | Описание |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Да | `super-secret-key` | Секрет Django |
| `DEBUG` | Да | `1` / `0` | Режим отладки |
| `ALLOWED_HOSTS` | Да | `localhost,127.0.0.1` | Разрешённые хосты (CSV) |
| `POSTGRES_DB` | Да | `app_db` | Имя БД |
| `POSTGRES_USER` | Да | `app_user` | Пользователь БД |
| `POSTGRES_PASSWORD` | Да | `securepassword` | Пароль БД |
| `POSTGRES_HOST` | Да | `db` | Хост БД (`db` в Docker) |
| `POSTGRES_PORT` | Да | `5432` | Порт БД |
| `CELERY_BROKER_URL` | Да | `redis://redis:6379/0` | Broker для Celery |
| `CELERY_RESULT_BACKEND` | Да | `redis://redis:6379/0` | Result backend Celery |
| `CORS_ALLOWED_ORIGINS` | Да | `http://localhost:5173,http://localhost:4173` | Разрешённые frontend-origin (CSV) |
| `CORS_ALLOW_CREDENTIALS` | Да | `True` | Разрешение credentials в CORS |

Пример `.env` для локальной связки с frontend:

```env
DJANGO_SECRET_KEY=change-me
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=app_db
POSTGRES_USER=app_user
POSTGRES_PASSWORD=securepassword
POSTGRES_HOST=db
POSTGRES_PORT=5432
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:4173,http://localhost:8000
CORS_ALLOW_CREDENTIALS=True
```

## 5. Быстрый запуск через Docker Compose

1. Перейдите в папку `backend`:

```bash
cd backend
```

2. Подготовьте `.env`:

```bash
cp .env.dist .env
```

3. Запустите контейнеры:

```bash
docker compose up --build -d
```

4. Примените миграции:

```bash
docker compose exec web python manage.py migrate
```

5. (Опционально) создайте администратора:

```bash
docker compose exec web python manage.py createsuperuser
```

6. Проверьте доступность API:
- Admin: `http://localhost:8000/admin/`
- JWT login endpoint: `http://localhost:8000/api/users/login/`

### Логи и состояние сервисов

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

## 6. Локальный запуск без Docker

Ниже сценарий, если PostgreSQL и Redis уже подняты отдельно.

1. Создайте и активируйте virtualenv:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Настройте `.env` (обратите внимание на хосты):
- `POSTGRES_HOST=localhost`
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/0`

4. Примените миграции:

```bash
cd app
python manage.py migrate
```

5. Запустите Django API:

```bash
python manage.py runserver 0.0.0.0:8000
```

6. В отдельных терминалах запустите Celery:

```bash
cd backend/app
celery -A app worker --loglevel=info
```

```bash
cd backend/app
celery -A app beat --loglevel=info
```

## 7. Интеграции и особенности

### JWT-аутентификация
- По умолчанию API ожидает `Authorization: Bearer <access_token>`.
- Токены выдаются через SimpleJWT.
- В текущих настройках `ACCESS_TOKEN_LIFETIME=999 days`, `REFRESH_TOKEN_LIFETIME=1000 days`.

### LLM-провайдеры
- `openai`: требуется `api_key`, `base_url` опционален.
- `deepseek`: требуется `api_key`, если `base_url` пустой, используется `https://api.deepseek.com`.
- `ollama`: `api_key` не нужен, если `base_url` пустой, используется `http://localhost:11434`.

### Git-провайдеры
- `github`: реализован (репозитории, PR, diff, публикация комментариев).
- `gitlab`: присутствует в enum/API, но методы провайдера пока `NotImplemented`.

## 8. Структура проекта

```text
backend/
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.dist
  app/
    manage.py
    app/                    # settings, urls, celery bootstrap
    users/                  # auth API
    code_hosts/             # workspace/integration/repository/MR логика
    llm/                    # LLM integrations + providers
    reviews/                # review pipeline, модели, Celery tasks
    common/                 # базовые общие модели
```

## 9. Частые проблемы

### `403`/CORS при запросах с frontend
Проверьте `CORS_ALLOWED_ORIGINS` в `.env`. Для dev обычно нужны:
- `http://localhost:5173`
- `http://localhost:4173`
- `http://localhost:8000`

### `connection to server at "db" failed`
Вы запускаете backend не в Docker, но оставили `POSTGRES_HOST=db`. Для локального запуска укажите `POSTGRES_HOST=localhost`.

### Ревью зависает в `queued`
Проверьте, что запущены `worker` и `redis`, и что Celery видит broker:

```bash
docker compose logs -f worker
```

### Ошибка `NotImplementedError` при GitLab-интеграции
В текущей реализации GitLab-провайдер не завершён. Используйте GitHub до завершения реализации GitLab.

### Ошибка публикации комментариев в PR
Проверьте токен GitHub и scope прав на создание комментариев в Pull Request.

## 10. Команды-шпаргалка

```bash
# Запуск всего стека
cd backend
docker compose up --build -d

# Миграции
docker compose exec web python manage.py migrate

# Остановка
cd backend
docker compose down

# Логи
cd backend
docker compose logs -f web
docker compose logs -f worker

# Тесты Django
cd backend/app
python manage.py test

# Форматирование
cd backend
black app
isort app
```
