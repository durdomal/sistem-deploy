# Sistem Core — правила репозитория

«Мозг» Sistem: FastAPI-приложение, оркеструет проекты Тараса через Project Packs, скиллы и мосты (VPS/n8n/Claude Code). Живёт на VPS `152.53.231.15` под `sistem.globria.biz`.

## Стек (фактический)
- **Python 3.13**, FastAPI 0.115, Pydantic v2, SQLAlchemy 2 (async)
- **Postgres + pgvector** (память, семантический поиск), **Redis + RQ** (очередь задач)
- JWT (python-jose, RS256, OAuth 2.1 + DCR — v1.1), passlib/bcrypt
- Упаковка: Docker + docker-compose (`db` + `redis` + `api` + `worker`)
- НЕ Node/Next.js. Фронта в этом репо нет.

## Структура
- `app/sistem/` — приложение: `main.py`, `config.py`, `routers/` (auth, projects, memory, command, skills, bridges, mcp, system), `services/` (в т.ч. `skill_resolver.py`, `bootstrap.py`)
- `app/tests/` — smoke-тесты по спринтам: `smoke_sprint1..3,7.py`, `smoke_oauth.py`
- `db/schema.sql` — Postgres-схема (users, projects, memory×3, skills, tasks, audit, bridges×3, billing)
- `schemas/project-pack.schema.json` — валидатор Project Pack; примеры в `examples/*.pack.yaml`
- `deploy/` — docker-compose, `.env.example`, `nginx-sistem.conf`, `scripts/bootstrap.sh`
- `docs/` — `ARCHITECTURE.md` (8 слоёв, решения, спринты), `INTEGRATIONS_SYNC.md`, `SPRINT-0-STATUS.md`, `PROJECT_PACK_SPEC.md`
- Родительская `../CLAUDE.md` — бизнес-контекст проектов; `../AGENTS_REGISTRY.md` — реестр агентов
- Мастер-очередь интеграций (источник истины по статусам): `D:\.claude\SISTEM_QUEUE.md`

## Тесты
- Полный стек локально не поднять без зависимостей → smoke-тесты рассчитаны на Docker/CI.
- Чистая логика (напр. `skill_resolver`) тестируется standalone: `PYTHONIOENCODING=utf-8` обязателен (Windows-консоль в cp1251 падает на юникоде).
- Smoke гоняют in-memory (`sqlite+aiosqlite`) с MOCK-мостами (`SISTEM_VPS_MOCK=1`, `SISTEM_N8N_MOCK=1`).

## Правила деплоя (ЖЁСТКО)
- **Никогда** `certbot --nginx` — только `certonly --webroot` (иначе сломает конфиги globria/ide/watersports).
- Порт 443 — **sslh**; реальный nginx на **:8443**.
- **Никогда** не пробрасывать `db`/`redis` наружу — только `127.0.0.1`.
- **Никогда** не коммитить `.env` — только `.env.example`. Секреты через `openssl rand`.
- Деплой на VPS: путь `/opt/sistem/`, через `bootstrap.sh` (идемпотентный) или GitHub→raw curl bridge.
- Пуш в `main` — осознанно; репо не форкнуто, remote `origin/main`.

## Стиль кода
- Отвечать/комментировать по-русски, кратко (как везде у Тараса).
- Ошибки — типизированные HTTP (не throw string); auth-провалы → чистый 401.
- Правки роутеров/сервисов → сверяйся со smoke соответствующего спринта.
