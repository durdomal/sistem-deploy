# Project Pack v1 — Спецификация

**Что это:** стандартизированное досье бизнеса/ниши, которое Sistem принимает на вход и использует во всех скиллах. Один формат — любая ниша.

Файл-формат: `YAML` (человекочитаемо) или `JSON` (для API). На входе конвертируется в JSON и валидируется JSON Schema (`schemas/project-pack.schema.json`).

---

## Пример (минимум)

```yaml
project:
  id: watersports-cb
  name: Watersports Costa Blanca
  niche: sup-rental
  status: active
  owner: taras

brand_pack:
  name: Watersports Costa Blanca
  palette: ["#0A6AA1", "#FFC857", "#111"]
  fonts: [Inter, "Playfair Display"]
  voice: friendly-locals
  logo_url: https://cdn.example.com/wcb-logo.svg

channels:
  instagram:
    handle: watersports.costablanca
  facebook:
    page_id: "123456789"

goals:
  primary: increase-bookings
  kpis:
    - name: weekly_bookings
      target: 25
```

---

## Полная схема (все поля)

```yaml
project:
  id: <slug, обязательно, [a-z0-9-]+>
  name: <string, обязательно>
  niche: <string, категория: sup-rental, car-import, lead-gen, restaurant, ...>
  status: active | paused | archived
  owner: <string, id пользователя-владельца>
  created_at: <ISO datetime>
  tags: [string, ...]

brand_pack:
  name: <string, обязательно>
  palette: [hex, ...]           # ["#0A6AA1", "#FFC857"]
  fonts: [string, ...]          # ["Inter", "Playfair Display"]
  voice: <string>               # short human tag: friendly-locals / premium-b2b / ...
  logo_url: <url>
  brand_pack_id: <slug>         # ссылка на переиспользуемый бренд-пак

catalog:
  products:
    - sku: <string>
      name: <string>
      price: <number>
      currency: <ISO4217, default EUR>
      description: <string>
      images: [url, ...]
      metadata: {…}             # свободный dict

audience:
  segments:
    - name: <string>            # "families with kids"
      demographic: <string>
      geo: <string>             # "Denia, Jávea, Moraira"
      insights: <string>        # свободный текст, что мы знаем

usps:
  - <string>                    # "первый в Дении оператор с русскоязычным сервисом"

channels:
  instagram:
    handle: <string>
    followers: <int>
    token: <string, optional, encrypted at rest>
  facebook:
    page_id: <string>
    token: <string, optional>
  tiktok:
    handle: <string>
  telegram:
    chat_id: <string>
    bot_token: <string, optional>
  website:
    url: <url>
    analytics_id: <string>
  google_business:
    place_id: <string>
  linkedin:
    company_id: <string>

competitors:
  - name: <string>
    url: <url>
    strengths: [string, ...]
    weaknesses: [string, ...]
    notes: <string>

goals:
  primary: <string>             # increase-bookings / grow-followers / win-deals
  secondary: [string, ...]
  kpis:
    - name: <string>            # weekly_bookings, cpl, cac
      target: <number>
      window: <string>          # week/month/quarter
      current: <number, optional>

budget:
  paid_ads_monthly: <number>
  currency: <ISO4217>
  per_channel:
    meta: <number>
    google: <number>
    tiktok: <number>
    …

voice_pack:
  examples:
    - <string>                  # эталонный текст
  taboos:
    - <string>                  # "не используем emoji 🌊 в подписях"
  tone: <string>                # свободный человеческий тег

integrations:                   # ключи внешних систем, encrypted at rest
  postiz_account_id: <string>
  higgsfield_workspace: <string>
  n8n_workflow_ids: [string, ...]

meta:
  version: 1
  updated_at: <ISO datetime>
  updated_by: <user id>
```

---

## Что обязательно (JSON Schema `required`)

Минимум для валидации:
- `project.id`
- `project.name`
- `project.niche`
- `project.status`
- `brand_pack.name`
- Хотя бы один непустой `channels.*`

Всё остальное — опционально, но чем больше заполнено, тем лучше скиллы.

---

## Правила ID

- `project.id` = `<kebab-case>`, глобально уникален на пользователя.
- Символы: `[a-z0-9][a-z0-9-]*`, макс. 48.

---

## Правила секретов

Поля `channels.*.token`, `channels.*.bot_token`, `integrations.*` — считаются секретами. При сохранении шифруются AES-GCM ключом из `.env` (`SISTEM_SECRETS_KEY`). При отдаче наружу — маскируются (`****abcd`), кроме прямого запроса владельца проекта.

---

## Миграции

Каждая версия схемы бампает `meta.version`. Migrator в Sistem Core (`migrations/pack/v1_to_v2.py`) конвертирует старые паки при загрузке. v1 — базовая.

---

## Импорт/экспорт

**Импорт:**
- `POST /users/{uid}/projects` — тело: JSON пака
- `POST /users/{uid}/projects/import` — тело: YAML (multipart `file` или raw text/yaml)

**Экспорт:**
- `GET /users/{uid}/projects/{pid}?format=yaml|json` (секреты замаскированы)
- `GET /users/{uid}/projects/{pid}/full?format=yaml|json` (для владельца, секреты открыты)

---

## Использование в скиллах

Каждый скилл получает `project_id` и вызывает `sistem_project_context(project_id)`. В ответе — пак с расшифрованными секретами (только для скилла на сервере, наружу не уходит).

Пример:
```
sistem_command("сделай пост в инсту про новый SUP-борд", project_id="watersports-cb")
  → skill_resolver: niche-content
  → niche-content(project_id="watersports-cb", topic="new SUP board")
    → sistem_project_context("watersports-cb")
      → brand_pack, voice_pack, channels.instagram, audience → генерация
```

---

*Схема живая. Изменения — через миграцию + бамп `meta.version`.*
