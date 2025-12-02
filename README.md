# app Django service

## Overview
- Django project named `app` with PostgreSQL backend.
- Environment variables live in `.env`, copy `.env.dist` for template.
- Docker setup spins up `web` (Gunicorn/Django) and `db` (PostgreSQL).

## Local usage
1. Copy `.env.dist` to `.env` and customize secrets.
2. Build and run with `docker-compose up --build`.
3. Apply migrations inside the `web` container: `docker-compose exec web python manage.py migrate`.
4. Access the application on `http://localhost:8000/`.

## File layout
```
backend/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── .env
├── .env.dist
├── .dockerignore
└── app/            # Django project
    ├── manage.py
    └── app/
        ├── __init__.py
        ├── settings.py
        ├── urls.py
        └── wsgi.py
```
