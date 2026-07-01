# Integrations Sync — Sistem ↔ SISTEM_QUEUE

**Что это.** Файл-мост между архитектурой Sistem (`ARCHITECTURE.md`) и мастер-очередью интеграций Тараса (`D:\.claude\SISTEM_QUEUE.md`).

**Правила:**
- `SISTEM_QUEUE.md` — **единственный источник истины** по статусам интеграций (⬜/🟡/✅/🔒/⏸/⛔/❌). Владеет research-чат.
- Этот файл — **как Sistem абсорбирует каждый пункт**: в каком спринте, куда вешает, что делает.
- Правится Sistem-чатом в конце каждого спринта.
- Расхождения (в очереди ✅, в Sistem не отражено — или наоборот) фиксируются здесь в разделе «Расхождения».

**Читать вместе с:** `ARCHITECTURE.md` §7 (Skill Library), §7bis (Integrations Registry), §11 (Спринты).

**Last sync:** 2026-07-01 (после Sprint 2 close).

---

## 1. Уже подключено к Cowork (✅ в очереди)

Live remote-коннекторы, работают уже сейчас. В Sprint 1 регистрируем их в БД `bridge_*` (без изменения коннекторов).

| Из очереди | В Sistem — куда | Спринт абсорбции |
|---|---|---|
| Higgsfield (изображения/видео/3D + Virality Predictor + Marketing Studio + Soul ID + Kling Avatar 2.0) | L7 Service Mesh; используется скиллами `content-reels`, `niche-content`, `site-landing`, `brand-assets`, `higgsfield-prompt` | Sprint 1 (регистрация) → Sprint 6 (обёртки) |
| Postiz | L7 Service Mesh; используется `content-distribution` (новый в S6) | Sprint 2 (n8n wiring) → Sprint 6 (скилл) |
| Gmail | L7 Service Mesh; `lead-outreach` reply flow | Sprint 6 |
| Notion (коннектор) | L7 Service Mesh; sync Project Pack ↔ Notion баз (опционально) | Sprint 6 |
| Google Drive / Box | L7; хранение brand assets Project Pack | Sprint 6 |
| Figma (Dev Mode) | L7; используется `web-designer`, `brand-assets` | Sprint 6 |
| Chrome MCP + computer-use | L8 Bridges (частично), L7 (частично) | Sprint 4 (Local PC bridge использует их как таргеты) |

## 2. Готовые скиллы (✅ в очереди A2) — база Skill Library v2

| Плагин | Скиллы | Что делает Sistem |
|---|---|---|
| `sistem-power-pack` v0.2.0 (30.06) | `content-reels`, `itv-deal-card`, `lead-outreach`, `marketing-audit`, `reels-rewrite`, `sales-funnel`, `site-landing` | Sprint 6: переупаковка в `sistem-power-pack-universal` v1.0 |
| `sistem-power-pack` v0.3 (01.07, апдейт research-чата) | `booking-agent`, `connector-setup`, `deep-research-runner`, `niche-comment-miner`, `premium-design-checklist`, `retainer-agency`, `self-improve-loop`, `sell-sites-localbiz`, `unit-economics` | Sprint 2: зарегистрированы в БД `skills` через bootstrap. Sprint 6: та же переупаковка. |
| `taras-toolkit` | `aeat-spanish-tax`, `content-translator-ru-es-de`, `higgsfield-prompt`, `itv-dealer-followup`, `watersports-content` | Sprint 6: интегрируются как есть; `watersports-content` обобщается в `niche-content` (project_id-агностик) |
| `web-studio` | `brand-assets`, `car-photo-studio`, `site-analytics`, `site-deploy`, `site-ux-review`, `web-designer`, `web-frontend`, `web-qa`, `web-seo-growth`, `web-studio-orchestrator` | Sprint 6: используются как есть; `web-studio-orchestrator` вызывается через `sistem_skill_invoke` |
| `car-export-sourcing` + `auto-import-pro` + `es-registration-cost` | Полный конвейер ITV | Sprint 6: остаются как ниша-специфичный флоу (запускаются через `sistem_command project=itv-cb`) |
| `ai-clerk` | Универсальный outreach | Sprint 6: становится ядром `lead-outreach v2` |

## 3. Нужны ключи Тараса (🔒 в очереди A3)

Пока не разблокированы — Sistem учитывает в архитектуре, но не вызывает. Как только Тарас даст ключ — переводим в 🟡, потом ✅.

| Из очереди | Что делаем когда есть ключ | Спринт |
|---|---|---|
| Apify MCP [115, 99] | Регистрируем в `bridge_n8n_workflows` через remote-коннектор; используем в лид-скрапе для Globria/ITV | Sprint 2 |
| Firecrawl MCP [125] | Основа для нового скилла `competitor-watch` | Sprint 6 |
| Meta Ads MCP [112] | Данные в `kpi-report` + управление кампаниями через `sistem_command` | Sprint 5 (дашборд) / Sprint 6 (скилл) |
| Google Ads MCP [112] | То же | Sprint 5 / 6 |
| ManyChat | Интеграция в `sales-funnel` (comment→DM) | Sprint 6 |
| Submagic ($12-19/мес) | Post-processing в `content-reels` (ES-субтитры) | Sprint 6 |
| productivity: Asana/Atlassian/ClickUp/Linear/Monday/Slack/Notion | Источники таск-фида в дашборд + Telegram-алерты | Sprint 5 |

## 4. Инструменты Claude Code (для CC Bridge)

| Из очереди | Роль | Спринт |
|---|---|---|
| Graphify [116] 🟡 | Индексация кодовых репо (×5–71 экономия). Работает только в CC. Sistem вызывает через `sistem_run_claude_code` | Sprint 3 (первый тест моста именно на нём) |
| free-claude-code / OpenRouter | Tiered-routing рутины на дешёвые модели в CC | Sprint 3 (опц.) |
| Remotion 🟡 | Моушн-графика кодом | Sprint 6 (опц. интеграция в `content-reels`) |

## 5. Higgsfield-стек (⬜ A5) — подключён, обёртки в Sprint 6

| Из очереди | Куда |
|---|---|
| Virality Predictor | Обёртка в `content-reels`/`niche-content` — валидация креатива перед публикацией |
| Soul ID | Обёртка в `brand-assets` — генерация маскота из brand_pack |
| Kling Avatar 2.0 | Замена HeyGen; обёртка в `content-reels` для talking-head формата |
| Marketing Studio | UGC-генерация; обёртка в `content-reels` |

## 6. Проектные интеграции (ФАЗА B в очереди)

Все идут через **Project Pack + скиллы + n8n workflows**. Sistem не переизобретает — оркестрирует.

**B1 Globria:**
- Google Maps→продажа сайтов [120] → n8n workflow (Sprint 2) + `ai-clerk` + `site-landing`
- AI-аудит→ретейнеры [99] → `marketing-audit` (готов)
- Self-improving prompt loop [112] → n8n cron + memory feedback (Sprint 2)
- B2B-аутрич в тихие ниши [1] → `lead-outreach` (готов)

**B2 ITV Costa Blanca:**
- AutoBello monitor (конкурент) → n8n workflow + `competitor-watch` (Sprint 2/6)
- `itv-deal-card` + `es-registration-cost` (готовы)
- UI UX Pro Max + 21st.dev [82] → в CC-bridge задачи (Sprint 3+)
- KREA 3D + AR Code [37, 36] / бесплатный `<model-viewer>` → assets в `catalog.products.metadata`
- «До→После» Kling О1 [53] → обёртка в `content-reels`
- Wholesaling UX-паттерн [95, 87, 28] → `sales-funnel` под ITV

**B3 Watersports:**
- Higgsfield workflow Soul→Kling [24] → скиллы `brand-assets` + `content-reels`
- Рилс-витрина + WhatsApp CTA (+22% CTR) → `content-reels` c CTA-хвостом
- Эксперт + двойные субтитры [32] → `content-reels` + Submagic (когда есть)
- Meta video funnel (ThruPlay) [10] → Meta Ads MCP (когда OAuth)
- ManyChat comment→DM [105] → `sales-funnel` (когда есть аккаунт)

**B4 SMM Bridge 2.0:**
- 12 AI-агентов маркетинга [91] → субагенты через `Agent` в скиллах
- Tripwire-лестница [9, 7, 44] → `sales-funnel` (готов)
- Майнинг ниши [123] YouTube Data API → n8n workflow (Sprint 2)
- n8n из YouTube [56] self-host на VPS → Sprint 2

**B5 Smart import:** ⏸ paused с 20.06.2026 — не занимаемся.

## 7. Расхождения и вопросы

Пусто на 2026-07-01. Заполняется когда живая очередь и Sistem-реальность расходятся.

## 8. Регламент синхронизации

**В начале каждого спринта:**
1. Sistem-чат читает `D:\.claude\SISTEM_QUEUE.md`
2. Помечает пункты, которые попадают в этот спринт, как 🟡 (частично) — обновляет очередь
3. Обновляет секцию «Спринты» в `ARCHITECTURE.md` если появились новые пункты

**В конце спринта:**
1. Перевод сделанных пунктов в ✅ в очереди
2. Апдейт этого файла (`INTEGRATIONS_SYNC.md`) — в раздел соответствующий пункту добавляется «✅ Sprint N — что сделано»
3. Расхождения — в §7

**Правки со стороны research-чата:**
- Он дописывает новые находки в `SISTEM_QUEUE.md`
- Sistem подхватывает на следующем ревью (не срочно, кроме ключевых блокеров)

---

*Файл живой. Последнее обновление — 2026-07-01 (Sprint 0 close, перед Sprint 1).*
