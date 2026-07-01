# sistem-power-pack-universal v1.0

Финальная упаковка Cowork-плагина для Sistem v1.0.

## Что даёт

4 навыка в Cowork Settings → Capabilities:
- **sistem** — универсальная точка входа. Zero-config: пиши что хочешь, Sistem сам подбирает.
- **kpi-report** — KPI прямо в чате как HTML-виджет.
- **content-distribution** — пост в N каналов проекта.
- **competitor-watch** — мониторинг конкурентов.

## Установка

1. Из терминала в этой папке: `zip -r sistem-power-pack-universal.plugin .` (Windows PowerShell: `Compress-Archive * sistem-power-pack-universal.zip; ren *.zip *.plugin`).
2. Cowork → Settings → Capabilities → Install plugin → выбрать файл.
3. Cowork → Customize → Connectors → Add Custom MCP:
   - Name: `sistem`
   - URL: `https://sistem.globria.biz/mcp`
   - Auth: Bearer <access_token> (получить один раз: `curl -X POST https://sistem.globria.biz/auth/login -d '{"email":"…","password":"…"}'`)
4. Удалить старый плагин `sistem-control` (если стоял из Sprint 1).

## Что заменяется в Sprint 6

- Плагин **sistem-power-pack** v0.3 (9 скиллов) остаётся отдельным — Sistem вызывает его через `cowork:sistem-power-pack:<skill>` handler. Не дублируем.
- Плагин **sistem-control** v1.0 (Sprint 1) — удалить, заменён этим.
