# Sistem Core (v1.0)

Мозг Sistem — FastAPI-приложение с Postgres+pgvector, Redis-очередью и docker-compose-стеком. Живёт на VPS `152.53.231.15` под доменом `sistem.globria.biz`.

## Что здесь

```
sistem-core/
├── app/                    # FastAPI приложение
│   ├── Dockerfile
│   ├── requirements.txt
│   └── sistem/
│       ├── main.py
│       ├── config.py
│       └── routers/        # auth, projects, memory, command, skills, bridges, system
├── db/
│   └── schema.sql          # PostgreSQL + pgvector, применяется при первом старте контейнера
├── deploy/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── nginx-sistem.conf
├── docs/
│   ├── ARCHITECTURE.md
│   └── PROJECT_PACK_SPEC.md
├── schemas/
│   └── project-pack.schema.json
├── scripts/
│   └── bootstrap.sh        # идемпотентный установщик на VPS
└── examples/
    └── watersports-cb.pack.yaml
```

## Что готово в Sprint 0

- ✅ Архитектурный документ + принятые решения
- ✅ Project Pack v1 spec + JSON Schema
- ✅ Полная Postgres-схема (users, projects, memory×3, skills, tasks, audit, bridges, billing)
- ✅ Скелет FastAPI (`/health`, `/status`, `/version` работают; остальные роуты — 501 «Not implemented, Sprint N»)
- ✅ docker-compose с db+redis+api+worker
- ✅ Nginx-конфиг для `sistem.globria.biz` (webroot-SSL, БЕЗ `--nginx`)
- ✅ Bootstrap-скрипт

## Что делает Тарас (деплой Sprint 0 на VPS)

1. **DNS.** Прописать A-запись `sistem.globria.biz` → `152.53.231.15`. Если поддомен `globria.biz` уже через Cloudflare — там же добавить.
2. **Пуш кода на VPS.** Через существующий `wcb-deploy`-стиль bridge (GitHub → raw curl) или scp. Целевой путь `/opt/sistem/`.
3. **Секреты.** Сгенерь пары и вставь в `/opt/sistem/deploy/.env`:
   ```bash
   openssl rand -base64 32              # POSTGRES_PASSWORD
   openssl rand -base64 32              # REDIS_PASSWORD
   openssl rand -base64 32              # SISTEM_SECRETS_KEY
   openssl genrsa -out /tmp/jwt.pem 2048 && cat /tmp/jwt.pem   # JWT_PRIVATE_KEY
   openssl rsa -in /tmp/jwt.pem -pubout                        # JWT_PUBLIC_KEY
   rm /tmp/jwt.pem
   ```
4. **Bootstrap.** `sudo bash /opt/sistem/scripts/bootstrap.sh`
5. **Проверка.** `curl -s https://sistem.globria.biz/health` → JSON с `ok:true, version:1.0.0-sprint0`.

## Правила деплоя (жёстко)

- **Никогда** `certbot --nginx` — только `certonly --webroot`. Иначе сломает существующие конфиги (globria, ide, watersports).
- **Никогда** не пробрасывать `db`/`redis` наружу. Только `127.0.0.1`.
- **Никогда** не коммитить `.env`. Только `.env.example`.

## Sprint 1 (следующий)

- Настоящая логика: auth (JWT), Projects CRUD с валидацией пака, Memory API, Skills registry, `/command` с базовым rule-based Skill Resolver
- Плагин `sistem-control` для Cowork (skill = точка входа `sistem_command`)
- Тест: `sistem audit project=watersports-cb` в Cowork → результат в чате
