---
name: sistem
description: Универсальная точка входа в Sistem — AI-OS Тараса. Триггеры любой запрос про проекты (Watersports, ITV, Globria, будущие). Пользователь пишет что хочет — Sistem сам подбирает скилл, проект, ресурсы. Использует MCP-коннектор `sistem` (URL sistem.globria.biz/mcp).
---

# Sistem — универсальная точка входа

Единый скилл-обёртка над Orchestrator-MCP. **Никогда не спрашивай пользователя "какой скилл?" или "какой проект?"** — Sistem резолвит сам.

## Первое действие всегда

`mcp__sistem__sistem_command` с сырым текстом. Ответ содержит `resolved_skill`, `project_id`, `task_id`, часто `html_artifact` для рендера в чате.

## Если Sistem вернул html_artifact

Отдай его пользователю как есть — inline HTML. Никаких пересказов.

## Если Sistem вернул `type:cowork_invoke`

Это значит нужно вызвать конкретный Cowork-скилл (marketing-audit, content-reels, site-landing и т.д.) с параметрами из `params` + контекст из `project_context`. Делай Skill-вызов сразу без переспроса.

## Ошибки

- `bridge.vps` failed → скажи "Sistem VPS bridge не отвечает, проверить `curl https://sistem.globria.biz/health`"
- 401 → токен просрочен, `POST /auth/login`
