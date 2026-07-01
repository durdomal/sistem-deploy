# Cowork плагины Sistem

## sistem-control (v1.0.0)

Единственный минимальный плагин: один скилл `sistem`, который вызывает Sistem Core через remote MCP.

**Установка (после Sprint 1 deploy):**
1. Упаковать папку в zip: `cowork-plugins/sistem-control/*` → `sistem-control.plugin`
2. Settings → Capabilities → Install plugin → выбрать файл
3. Customize → Connectors → Add Custom MCP:
   - Name: `sistem`
   - URL: `https://sistem.globria.biz/mcp`
   - Auth: Bearer <access_token> (получить `POST /auth/login`)

**Что делает:** пользователь пишет свободный текст, Sistem сам подбирает скилл, проект, ресурсы.

**После Sprint 6** — заменяется на `sistem-power-pack-universal.plugin` (v1.0), который содержит и точку входа, и универсальные версии всех бизнес-скиллов.
