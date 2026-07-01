---
name: sistem
description: Единая точка входа в Sistem Core (Тарасова AI-OS). Триггеры — "sistem ...", "система ...", "system ...", любая команда работы над проектами Тараса (Watersports/ITV/Globria). Сам подбирает скилл, проект и ресурсы — пользователь просто пишет что хочет и получает результат. Использует MCP-коннектор `sistem` (URL sistem.globria.biz/mcp, регистрируется отдельно в Customize → Connectors).
---

# Sistem — точка входа

## Что этот скилл делает

Вызывает Sistem Core через remote MCP-коннектор `sistem`. Пользователь пишет свободный текст — Sistem сам:
1. Резолвит какой скилл нужен (LLM-router + rule-based fallback)
2. Резолвит проект (по имени/нише в тексте или по контексту сессии)
3. Ставит задачу в очередь на VPS
4. Возвращает task_id и предпросмотр результата

## Требования

Перед первым использованием Тарас должен:
1. Задеплоить Sistem Core на VPS: `sistem.globria.biz`. Проверить: `curl -s https://sistem.globria.biz/health` → `{"ok":true,…}`.
2. Зарегистрировать remote MCP в Cowork: **Customize → Connectors → Custom MCP**:
   - Name: `sistem`
   - URL: `https://sistem.globria.biz/mcp`
   - Auth: `Bearer <access_token>` (получить через `POST /auth/login` разово)
   - Approval: Needs approval (по умолчанию)

## Как звать

Один тул: `mcp__sistem__sistem_command` (JSON-RPC `tools/call` `{name:"sistem_command", arguments:{text,project_id?,channel}}`).

Дополнительные — редкие: `sistem_status`, `sistem_project_context`, `sistem_query_memory`, `sistem_log_event`, `sistem_skill_invoke`.

## Правила поведения

**Первый шаг всегда** — `sistem_command` с сырым текстом пользователя. Пример:

Пользователь: «сделай рилс про SUP-борд для watersports»
→ вызов `sistem_command({text: "сделай рилс про SUP-борд для watersports"})`
→ Sistem автоопределит `project=watersports-cb`, `skill=content-reels`, поставит task
→ ответ содержит `task_id` и превью `resolved_skill`

**НЕ спрашивай у пользователя**: какой скилл, какой проект. Sistem сам решает. Если Sistem вернул `project_id=null` и это не оперативная команда (например: «покажи статус») — тогда переспроси у пользователя один раз.

**НЕ вызывай** `sistem_skill_invoke` руками, если сработал `sistem_command` — он сам поставит правильный скилл.

**Проверка статуса задачи:** после `sistem_command` вернулся `task_id` — если задача не выполнится за 60 сек, скажи пользователю «Задача в очереди, проверить статус: `sistem_command "status <task_id>"`».

**Ошибки:**
- `401` → токен просрочен, Тарасу заново `POST /auth/login`
- `404 project` → sistem не нашёл проект по тексту; переспроси
- Connection refused → sistem_core лежит; предложи пользователю выполнить `curl https://sistem.globria.biz/health` для диагностики

## Никаких игрушек

Не создавай отдельные визуализации/дашборды/панели без явного запроса. Если пользователь просит «покажи KPI» — вызывай `kpi-report` скилл через `sistem_command`, тот вернёт готовый HTML-artifact.
