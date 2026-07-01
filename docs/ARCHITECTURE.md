# Sistem v1.0 — Architecture

**Owner:** Тарас (Costa Blanca, ES)
**Version:** 1.0 — Sprint 0 draft
**Дата:** 2026-07-01
**Статус:** утверждено на Sprint 0 (после ответов на 4 вопроса)

---

## 0. Что это

**Sistem** — универсальная AI-операционная система для предпринимателя. Один мозг, много каналов ввода, много исполнителей. Проект-агностичное ядро: активные бизнесы (Watersports, ITV, Globria) — обкаточные песочницы, не хардкод.

**Цель v1.0:** из любого канала (Cowork chat / Dispatch mobile / Telegram / веб) отдать команду вроде «sistem audit project=watersports» и получить результат, при этом система сама решает какой скилл вызвать, на какой машине его исполнить, что сохранить в память.

---

## 1. Принятые решения (Sprint 0)

| # | Вопрос | Ответ | Следствие |
|---|--------|-------|-----------|
| 1 | A (personal) или B (SaaS-ready)? | **B** | Multi-user в схеме БД, JWT auth, тенантность в роутах с первого дня |
| 2 | Домен Sistem Core | **sistem.globria.biz** | Поддомен на существующем VPS, бесплатно, SSL через Let's Encrypt (`certonly`, не `--nginx`) |
| 3 | Порядок бриджей | VPS → n8n → Claude Code → Local PC | Дешёвое и быстрое первым |
| 4 | Бюджет инфры | **€0** на старте | Всё на текущем Netcup VPS (152.53.231.15) |

---

## 2. Восемь слоёв (карта)

```
┌──────────────────────────────────────────────────────────────┐
│ L1  CHANNELS   Cowork · Dispatch · Telegram · Web · (Voice)  │
├──────────────────────────────────────────────────────────────┤
│ L2  SISTEM CORE (VPS)                                        │
│     Orchestrator · Project Registry · Memory · Skill         │
│     Resolver · Audit · Auth                                  │
├──────────────────────────────────────────────────────────────┤
│ L3  ORCHESTRATOR-MCP  (remote MCP в Cowork/CC)               │
├──────────────────────────────────────────────────────────────┤
│ L4  SKILL LIBRARY v2  (параметризованные, project-agnostic)  │
├──────────────────────────────────────────────────────────────┤
│ L5  PROJECT REGISTRY  (Project Pack v1 YAML/JSON)            │
├──────────────────────────────────────────────────────────────┤
│ L6  MEMORY LAYER  universal · project · cross-project        │
├──────────────────────────────────────────────────────────────┤
│ L7  SERVICE MESH  n8n · Postiz · Higgsfield-proxy · TG-бот   │
├──────────────────────────────────────────────────────────────┤
│ L8  BRIDGES  VPS · Claude Code · Local PC · n8n              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Sistem Core (L2) — детали

### 3.1 Стек
- **Runtime:** Python 3.12
- **Web:** FastAPI + Uvicorn
- **DB:** PostgreSQL 16 + pgvector
- **Кэш/очередь:** Redis 7 + RQ (Celery если позже нужны сложные графы)
- **Auth:** JWT (RS256), bcrypt для паролей, refresh-токены в Redis
- **Observability:** OpenTelemetry → Postgres таблица `audit_log`, Sentry (по желанию)
- **Деплой:** docker-compose на VPS, за nginx с SSL

### 3.2 Компоненты
1. **Orchestrator** — принимает `POST /command`, парсит команду, определяет `project_id` + `skill` + `bridge`, кладёт задачу в очередь, возвращает `task_id`.
2. **Project Registry** — CRUD проектов и Project Pack (JSON Schema валидация на входе).
3. **Memory Layer** — три уровня (см. §5). Postgres + pgvector.
4. **Skill Resolver** — маппинг «команда → скилл + параметры». MVP: правила в YAML, позже — LLM-роутер.
5. **Bridge Router** — по типу таргета (`vps` / `cc` / `pc` / `n8n`) шлёт исполнение в нужный bridge с audit.
6. **Auth** — JWT, роли `owner|admin|operator|viewer`, per-project ACL.
7. **Audit Log** — все команды, вызовы бриджей, результаты, ошибки → Postgres.

### 3.3 Ключевые эндпоинты (v1)

```
# System
GET  /health                          # liveness
GET  /status                          # снимок: очередь, бриджи, БД, версия
POST /events                          # приём событий от бриджей/n8n

# Auth
POST /auth/login
POST /auth/refresh

# Command (главная точка входа)
POST /command                         # {text, project_id?, channel} → {task_id}
GET  /tasks/{task_id}                 # статус/результат

# Projects
GET    /users/{uid}/projects
POST   /users/{uid}/projects          # тело — Project Pack (валидируется JSON Schema)
GET    /users/{uid}/projects/{pid}
PUT    /users/{uid}/projects/{pid}
DELETE /users/{uid}/projects/{pid}

# Memory
GET  /users/{uid}/memory/universal
GET  /users/{uid}/memory/projects/{pid}?query=&limit=
POST /users/{uid}/memory/projects/{pid}
GET  /users/{uid}/memory/insights     # cross-project

# Skills
GET  /skills                          # список зарегистрированных
POST /skills/{name}/invoke            # прямой вызов (обход роутера)

# Bridges
POST /bridge/vps/{host}/run
POST /bridge/cc/run
POST /bridge/pc/{pc_id}/run
POST /bridge/n8n/trigger/{workflow}
```

Все `/users/{uid}/…` роуты enforce'ят JWT.sub == uid или роль `admin`.

---

## 4. Orchestrator-MCP (L3)

Единственный remote MCP-коннектор в Cowork. Регистрируется в **Customize → Connectors → Custom MCP**, URL: `https://sistem.globria.biz/mcp`.

Универсальные тулы:
```
sistem_command(text, project_id?, channel="cowork")
sistem_status()
sistem_project_context(project_id)
sistem_query_memory(project_id, query, limit=10)
sistem_log_event(project_id, event)
sistem_run_on_vps(host, cmd)
sistem_run_claude_code(prompt, target_machine="vps", cwd?)
sistem_run_on_pc(pc_id, cmd)
sistem_trigger_n8n(workflow, payload)
sistem_skill_invoke(skill, project_id, params)
```

Sprint 1 отгружает первые 5 (без бриджей). Бриджи — Sprint 2/3/4.

---

## 5. Memory Layer (L6)

Три уровня, все в Postgres:

| Уровень | Таблица | Что | Кто пишет |
|---------|---------|-----|-----------|
| Universal | `memory_universal` | Про пользователя (Тарас, autónomo, языки, предпочтения) | Пользователь + автоматически |
| Project | `memory_project` (тегируется `project_id`) | Активность/факты по проекту | Скиллы, задачи, ручные заметки |
| Cross-project | `memory_insights` | Паттерны между проектами | Batch-job (nightly) |

Все таблицы имеют `embedding vector(1536)` для семантического поиска через pgvector.

**Retention:** universal — вечно; project — вечно, но с флагом `active`; insights — 90 дней (пересчитываются).

---

## 6. Project Pack v1 (L5)

Формат — JSON (YAML поддерживается на вход, конвертируется). Спека и JSON Schema — в `docs/PROJECT_PACK_SPEC.md` + `schemas/project-pack.schema.json`.

Ключевые разделы: `project`, `brand_pack`, `catalog`, `audience`, `usps`, `channels`, `competitors`, `goals`, `budget`, `voice_pack`.

Обязательные поля минимума: `project.id`, `project.name`, `project.niche`, `project.status`, `brand_pack.name`, минимум один `channels.*`.

Загрузка: `POST /users/{uid}/projects` с телом-паком → JSON Schema валидация → сохранение в БД + генерация эмбеддингов ключевых текстовых полей для memory.

---

## 7. Skill Library v2 (L4)

Каждый скилл — функция `(project_id, params) → result`. Регистрация — в БД (`skills`) + плагин `sistem-power-pack-universal` (Cowork). Orchestrator-MCP умеет их звать через `sistem_skill_invoke`.

**Sprint 6 НЕ создаёт скиллы с нуля** — он абсорбирует уже готовые из существующих Cowork-плагинов и переводит в единую параметризованную форму `(project_id, params) → result`.

### 7.1 Уже готовые скиллы (база v2)

Источник статусов — `D:\.claude\SISTEM_QUEUE.md` (живой файл, обновляется research-чатом).

**Плагин `sistem-power-pack` v0.2.0** ✅ установлен 30.06.2026:
`content-reels` · `itv-deal-card` · `lead-outreach` · `marketing-audit` · `reels-rewrite` · `sales-funnel` · `site-landing`

**Плагин `taras-toolkit`**:
`aeat-spanish-tax` · `content-translator-ru-es-de` · `higgsfield-prompt` · `itv-dealer-followup` · `watersports-content`

**Плагин `web-studio`**:
`brand-assets` · `car-photo-studio` · `site-analytics` · `site-deploy` · `site-ux-review` · `web-designer` · `web-frontend` · `web-qa` · `web-seo-growth` · `web-studio-orchestrator`

**Плагины-конвейеры**: `car-export-sourcing`, `auto-import-pro` (+ `es-registration-cost`), `ai-clerk`.

**Anthropic base skills**: `docx`, `xlsx`, `pptx`, `pdf`, `canvas-design`, `theme-factory`, `skill-creator`, `learn`, `mcp-builder`, `web-artifacts-builder`, `doc-coauthoring`, `deep-research`.

**Server/deploy skills**: `ssh-connect`, `globria-deploy`, `wcb-deploy`, `nginx-manager`, `server-health`, `itv-*` роли.

### 7.2 Что добавляем в Sprint 6

Три новых скилла (нет аналога в очереди):
- `content-distribution` — публикация одного поста в N каналов проекта (Postiz как исполнитель)
- `competitor-watch` — мониторинг конкурентов из Project Pack (Firecrawl + Apify когда есть ключи)
- `kpi-report` — KPI-отчёт по проекту из `memory_project` + `goals.kpis`

Плюс отобранные топ-скиллы **МЕТАФЛОРА** [114] — research-чат отбирает и упаковывает в `sistem-power-pack-universal` v1.0.

---

## 7bis. Integrations Registry

**Live source:** `D:\.claude\SISTEM_QUEUE.md`. Здесь — карта распределения по слоям и статус на 2026-07-01. Live-статусы всегда сверяются с очередью в начале каждого спринта (см. §14 Регламент).

### L7 — Service Mesh (исполнители на VPS / remote MCP в Cowork)

| Интеграция | Статус | Роль в Sistem | Абсорбируется в |
|---|---|---|---|
| Higgsfield | ✅ подключён | Генерация изображений/видео/3D, Virality Predictor, Marketing Studio, Soul ID, Kling Avatar 2.0 | Sprint 2 (proxy), Sprint 6 (обёртки в скиллах) |
| Postiz | ✅ подключён | Автопостинг соцсетей, планировщик | Sprint 2 (n8n), Sprint 6 (`content-distribution`) |
| n8n (self-host) | ⬜ | Workflow-движок (500+ интеграций) | Sprint 2 |
| Gmail | ✅ | Черновики/поиск/ярлыки | Sprint 5 (`lead-outreach` reply flow) |
| Notion (коннектор) | ✅ | Базы, страницы, поиск | Sprint 6 (project sync) |
| Google Drive / Box | ✅ | Файлы | Sprint 6 (Project Pack assets) |
| Figma (Dev Mode) | ✅ | Дизайн-контекст | Sprint 6 (`web-designer`) |
| Chrome MCP + computer-use | ✅ | Браузер + десктоп | Sprint 4 (Local PC bridge) |
| Apify MCP | 🔒 нужен ключ | Веб-скрейпинг лидов | Sprint 2 (n8n workflows) |
| Firecrawl MCP | 🔒 нужен ключ | Краулер сайтов конкурентов | Sprint 6 (`competitor-watch`) |
| Meta Ads MCP | 🔒 OAuth | Управление рекламой | Sprint 5+ (`kpi-report`) |
| Google Ads MCP | 🔒 OAuth + dev token | Управление рекламой | Sprint 5+ (`kpi-report`) |
| ManyChat | 🔒 аккаунт | Comment→DM автоворонка | Sprint 6 (`sales-funnel`) |
| Submagic | 🔒 оплата | Субтитры ES | Sprint 6 (`content-reels` post-processing) |
| productivity: Asana/Atlassian/ClickUp/Linear/Monday/Slack | ⚠️ OAuth | Таск-трекеры + чаты | Sprint 5 (Telegram-бот + дашборд) |

### L8 — Bridges

| Инструмент | Статус | Роль | Sprint |
|---|---|---|---|
| Graphify [116] | 🟡 в Claude Code | Индексация репо (×5–71 экономия) — только в CC, не в Cowork | Sprint 3 — тест через CC bridge |
| claude-mem | ⚠️ отложено | Дубль авто-памяти, AGPL — не берём | — |
| RuFlow / claude-flow | ⏸ | Развенчан аудитом — берём только идею tiered-routing | — |
| Remotion | 🟡 | Моушн-графика кодом | Sprint 6 (опционально) |

### L4 — Skill Library v2 (плагины) — см. §7.1 выше

### L5 — Project Registry (внешние данные для паков)

| Источник | Роль |
|---|---|
| Google Maps | Data source для B1 «продажа сайтов» + `lead-outreach` |
| YouTube Data API | Майнинг ниши для B4 SMM Bridge |
| KREA / AR Code / `<model-viewer>` | 3D-витрина авто для B2 ITV — assets в `catalog.products.metadata` |

### Что НЕ берём (⛔/❌) — зафиксировано

Локальные stdio-MCP в Cowork (basic-memory/uvx/npx — роняют штаб, инцидент 30.06); claude-mem в Cowork; OpenClaw; Arcads/HeyGen/InVideo/Weave/Manus (дублируют Higgsfield); фейк-трейдинг Polymarket; faceless YouTube AI-slop; дропшиппинг Китай→ЕС.

**Правило Cowork:** только навыки-плагины (Settings→Capabilities) + remote-коннекторы (Customize→Connectors). Никаких локальных stdio-MCP.

---

## 8. Bridges (L8) — модель безопасности

Каждый bridge имеет:
1. **Allowlist команд** — regex или whitelist.
2. **Allowlist хостов/PC** — по `host` / `pc_id`.
3. **Audit log** — каждый вызов пишется в `audit_log` с before/after снапшотом.
4. **Timeout** — жёсткий (по умолчанию 60 сек, конфигурируется).
5. **Rate limit** — на пользователя и на bridge.

**Bridge порядок реализации:** VPS (Sprint 2) → n8n (Sprint 2) → Claude Code (Sprint 3) → Local PC (Sprint 4).

**Local PC Bridge** = daemon `sistem-local-agent` (Python+FastAPI) на Windows, exposed через Cloudflared tunnel. Регистрируется в БД: `pc_id`, `tunnel_url`, `public_key`. Взаимная аутентификация через mTLS сертификаты, выпущенные Sistem Core.

---

## 9. SaaS-ready заклад (сразу)

Хотя v1.0 персональная — все таблицы имеют `user_id`, роуты — `/users/{uid}/…`, auth — JWT. Биллинг-хуки (`billing_events`) как заглушки. Onboarding-флоу в дашборде — Sprint 5.

Что дополнительно нужно для «включить SaaS»:
- Stripe интеграция (webhook на `/billing/stripe`) — таблица `subscriptions`
- Landing на `usesistem.com` (или отдельный) — Next.js
- Публичная документация (Mintlify) — реюзаем `sistem.globria.biz/docs`
- Тарифы + квоты (rate-limit по плану)
- Email/support flow

Всё это НЕ в v1.0. Мы просто не рушим совместимость.

---

## 10. Развёртывание

**VPS 152.53.231.15**, отдельный docker-compose (не трогаем globria/postiz):
```
/opt/sistem/
├── docker-compose.yml
├── .env                # секреты
├── app/                # FastAPI (bind mount или image)
├── db/init/            # SQL миграции
├── nginx/
└── data/
    ├── postgres/
    └── redis/
```

**Nginx (глобальный `/etc/nginx/`):** новый `server_name sistem.globria.biz;` в отдельном файле `/etc/nginx/sites-available/sistem.conf`, симлинк в `sites-enabled/`. Proxy_pass на `127.0.0.1:8010` (порт Sistem Core). **Никогда** `certbot --nginx` — только `certbot certonly --webroot`, руками вписываем `ssl_certificate` в конфиг.

**SSL:** Let's Encrypt через существующий `certonly` флоу.

**Порт:** 8010 (внутренний, не публиковать в сеть).

---

## 11. Спринты (карта — обрезано 2026-07-01)

**Директива Тараса (2026-07-01):**
- Zero-config UX. Пользователь пишет что хочет — система сама подбирает скилл, проект, ресурсы. Без "какой скилл использовать?".
- Никаких «игрушек» — только то, что двигает функциональность или экономит время.
- Отдельный веб-дашборд и Telegram-бот НЕ нужны — Dispatch и inline HTML-artifacts в чате всё покрывают.
- Local PC Bridge — не обязателен для v1.0, откладывается в v1.1.

Столбец «Из очереди» — пункты `SISTEM_QUEUE.md`. Live-статусы там.

| # | Название | Длит. | Deliverable | Из очереди |
|---|----------|-------|-------------|-------------|
| 0 | Foundation | ✅ done | Архитектура, Schema, DB, скелет Core | — |
| 1 | Orchestrator MVP (расширен) | 1 нед | Auth + Projects CRUD + Memory + **LLM-router + auto project switcher** + 5 core-тулов Orchestrator-MCP + плагин `sistem-control`. Zero-config: пользователь пишет фразой, система резолвит всё сама. | Регистрация уже подключённых remote-коннекторов (Higgsfield/Postiz/Gmail/Notion/Figma/GDrive/Chrome) в БД `bridge_*` |
| 2 | VPS Bridge + n8n | 1 нед | VPS-bridge + n8n + 5-10 workflows | ФАЗА B workflows: B1, B2 AutoBello monitor, B4 майнинг ниши YouTube [123, 56]. Apify/Firecrawl когда есть ключи |
| 3 | Claude Code Bridge | 1 нед | `claude-code-server` daemon + тест на Graphify | Graphify [116], free-claude-code tiered-routing |
| 4 | ~~Local PC Bridge~~ | — | Отложен в **v1.1**. Если понадобится — доделаем после реальной работы Sistem с 3 проектами. | — |
| 5 | HTML-visuals inline (было: Web Dashboard + Telegram-бот) | 3 дня | Скиллы умеют возвращать HTML-artifact (KPI-график, статус проектов, лента событий) прямо в Cowork-чат по запросу. **Никакого отдельного веб-дашборда и Telegram-бота.** | productivity-плагин (Asana/ClickUp/Linear/Monday/Slack/Notion) — OAuth со стороны Тараса когда будет нужен |
| 6 | Skills refactor | 1 нед | Абсорбция `sistem-power-pack` v0.2.0 (7) + `taras-toolkit` + `web-studio` + отобранные топ-10 **МЕТАФЛОРА** [114] → `sistem-power-pack-universal` v1.0. +3 новых: `content-distribution`, `competitor-watch`, `kpi-report`. Higgsfield-стек как обёртки. ManyChat/Submagic — если разблокированы. | A2, A5, A6, ФАЗА B навыковые |
| 7 | Universality check | 1 день | Быстрая валидация: 4-й тестовый Project Pack в новой нише (ресторан Costa Blanca), убеждаемся что скиллы работают без хардкода. | — |

**Новый срок Sistem v1.0: 4-5 недель** (было 6-8).

**Что явно не в v1.0:** Web Dashboard как отдельный сайт, Telegram-бот, Local PC Bridge, HUD/eDEX/голос, Obsidian-интеграция, МЕТАФЛОРА как самостоятельный интерфейс (используется как источник скиллов, наружу не выходит).

**Регламент синхронизации с `SISTEM_QUEUE.md`:** в начале каждого спринта Sistem-чат читает очередь и переводит абсорбируемые пункты в 🟡; в конце — пишет ✅ и апдейтит `INTEGRATIONS_SYNC.md`. Research-чат при новых находках пишет в очередь; Sistem подхватывает на следующем ревью.

---

## 12. Связи с другими чатами

| Чат | Роль | Точка стыка |
|-----|------|-------------|
| `SMM worker and AI agent` | SMM Bridge 2.0 (Postiz) | Postiz как Service Mesh компонент, не переделывать |
| `Claude Code and Cowork customization research` | Находки + скиллы + плагины | Skill Library v2 использует их наработки |
| `watersports-costablanca` | сайт SUP | Project Pack от него → Sistem Registry |
| `ImportTradeVehiculus site` + `ITV` | ITV сайт+inventory | Project Pack ↑ |
| `Daily server health` + `Daily tasks triage` | scheduled | Перенос в n8n после Sprint 2 |

---

## 13. Что не в скоупе v1.0

- Voice (eDEX-UI + ElevenLabs) — Sprint 8+
- Мультиязычный UI дашборда (только английский на MVP, локализация после)
- Мобильное нативное приложение (используем Dispatch)
- LLM-роутер вместо rule-based Skill Resolver
- Автомасштаб (одна нода хватает надолго)

---

*Документ живой. Правки — PR в этот же файл.*
