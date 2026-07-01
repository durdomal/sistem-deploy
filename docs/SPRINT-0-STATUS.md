# Sprint 0 — статус

**Дата:** 2026-07-01
**Продолжительность:** 1 день (планировали 3-5)
**Результат:** ✅ готово к передаче Тарасу для деплоя на VPS.

---

## Что готово (в этом space)

| # | Артефакт | Файл |
|---|----------|------|
| 1 | Архитектура (8 слоёв, 4 решения) | `docs/ARCHITECTURE.md` |
| 2 | Project Pack v1 спека | `docs/PROJECT_PACK_SPEC.md` |
| 3 | JSON Schema валидатор | `schemas/project-pack.schema.json` |
| 4 | Postgres схема (~20 таблиц) | `db/schema.sql` |
| 5 | FastAPI скелет | `app/sistem/*` |
| 6 | Dockerfile + requirements | `app/Dockerfile`, `app/requirements.txt` |
| 7 | docker-compose (db+redis+api+worker) | `deploy/docker-compose.yml` |
| 8 | `.env.example` | `deploy/.env.example` |
| 9 | Nginx-конфиг (webroot SSL) | `deploy/nginx-sistem.conf` |
| 10 | Bootstrap-скрипт | `scripts/bootstrap.sh` |
| 11 | Эталонный пример пака | `examples/watersports-cb.pack.yaml` |
| 12 | README | `README.md` |
| 13 | Память обновлена | `memory/project-sistem-core.md` |

## Проверки, которые я прогнал

- ✅ JSON Schema валидна, пример `watersports-cb.pack.yaml` проходит без ошибок.
- ✅ FastAPI-скелет стартует: `/health` → 200 (JSON), `/status` → 200 (компоненты), заглушки роутов → 501 с корректным номером спринта, OpenAPI 18 путей.
- ✅ Postgres schema покрывает все компоненты: users, projects, memory×3, skills, tasks, audit, bridges×3, billing.

## Что делает Тарас (деплой на VPS)

Один заход по SSH, ~15 минут:

```bash
# 1. DNS: A-запись sistem.globria.biz → 152.53.231.15  (через Cloudflare/панель Netcup)

# 2. На VPS — забрать код (через wcb-deploy bridge или scp)
sudo mkdir -p /opt/sistem
sudo rsync -a /path/to/sistem-core/ /opt/sistem/   # или свой мост

# 3. Секреты в /opt/sistem/deploy/.env
cd /opt/sistem/deploy
cp .env.example .env
nano .env
# впиши:
#   POSTGRES_PASSWORD  →  openssl rand -base64 32
#   REDIS_PASSWORD     →  openssl rand -base64 32
#   SISTEM_SECRETS_KEY →  openssl rand -base64 32
#   JWT_PRIVATE_KEY/PUBLIC_KEY  →  openssl genrsa + rsa -pubout

# 4. Bootstrap
sudo bash /opt/sistem/scripts/bootstrap.sh

# 5. Проверка
curl -s https://sistem.globria.biz/health
# ожидаем: {"ok":true,"version":"1.0.0-sprint0","time":"..."}
```

## Точки риска

1. **DNS.** Если A-запись не прописана — certbot упадёт. Проверь `dig sistem.globria.biz` до `bootstrap.sh`.
2. **Порт 8010.** Убедись что не занят (`ss -tlnp | grep 8010`).
3. **Nginx конфликты.** Bootstrap делает `nginx -t` перед reload — если что-то в существующих конфигах (globria/ide/watersports) сломано, увидим сразу и не сломаем прод.
4. **certbot.** Скрипт использует `certonly --webroot` строго — не тронет существующие сертификаты globria.

## Блокеры для Sprint 1

Ничего не блокирует старт Sprint 1 в space, **но** для end-to-end теста (`sistem audit project=watersports` из Cowork) нужно:

- ✅ VPS-деплой Sprint 0 (пункт «делает Тарас» выше)
- 🟡 URL Sistem Core в Cowork Custom MCP (я подготовлю в Sprint 1, но регистрирует Тарас через Customize → Connectors)

## Что дальше — Sprint 1 (1 неделя)

1. Auth: JWT-роут `/auth/login` + `/auth/refresh`, bootstrap-юзер (Тарас) с bcrypt-хешем.
2. Projects CRUD с валидацией JSON Schema на входе + AES-GCM шифрование секретов.
3. Memory API: universal + project (запись/чтение/семантический поиск через pgvector).
4. Skills registry + rule-based Skill Resolver v0.
5. `POST /command` — принимает текст, резолвит скилл, ставит задачу в очередь RQ, возвращает `task_id`.
6. Плагин Cowork `sistem-control` с 5 core-тулами Orchestrator-MCP: `sistem_command`, `_status`, `_project_context`, `_query_memory`, `_log_event`.
7. Тест: команда в Cowork → результат в чате.

**Пингую только на конце Sprint 1** (или раньше, если упрёмся в реальный блок).
