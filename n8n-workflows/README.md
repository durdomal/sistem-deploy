# n8n workflows для Sistem

5 базовых workflow для Sprint 2. Импорт: n8n UI → Workflows → Import from File.

| # | Файл | Триггер (webhook) | Что делает | Требует env |
|---|------|-------------------|------------|-------------|
| 1 | `01-daily-server-health.json` | `sistem/daily-server-health` | Дёргает Sistem→VPS bridge с health-командами, отправляет Telegram-alert при аномалии | `SISTEM_JWT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT` |
| 2 | `02-google-maps-lead-scan.json` | `sistem/gmaps-lead-scan` | Ищет бизнесы в Google Maps через Apify, возвращает нормализованных лидов | `APIFY_TOKEN` |
| 3 | `03-postiz-schedule.json` | `sistem/postiz-schedule` | Планирует пост в Postiz на дату/время | `POSTIZ_BASE_URL`, `POSTIZ_API_KEY` |
| 4 | `04-competitor-monitor.json` | `sistem/competitor-monitor` | Firecrawl-scrape сайта конкурента → markdown snapshot | `FIRECRAWL_API_KEY` |
| 5 | `05-kpi-collector.json` | `sistem/kpi-collector` | Собирает KPI по источникам (Meta Ads/GA4/…) — сейчас с stub, реальные интеграции по OAuth | Ключи по мере получения |

## Регистрация в Sistem

После импорта в n8n получить webhook_url (Production URL) и вставить в БД:
```sql
INSERT INTO bridge_n8n_workflows (user_id, workflow_id, name, webhook_url, description)
VALUES ('<user_id>', 'daily-server-health', 'Daily Server Health',
        'https://n8n.globria.biz/webhook/sistem/daily-server-health', 'Sprint 2 base workflow');
```

Или через будущий admin-эндпоинт `POST /users/{uid}/n8n/register` (не в v1.0 API, добавим позже).

## Установка cron'а на workflow

n8n UI → Workflow → Schedule Trigger — стандартно, для health например `0 */6 * * *` (каждые 6 часов).

## Что дальше (Sprint 6+)

Добавляем workflow под каждый ФАЗА B пункт из `SISTEM_QUEUE.md`: майнинг ниши через YouTube Data API, self-improving prompt loop, Meta funnel prep.
