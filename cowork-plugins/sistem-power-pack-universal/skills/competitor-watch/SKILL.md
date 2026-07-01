---
name: competitor-watch
description: Мониторинг конкурентов из Project Pack. Триггеры "мониторинг конкурент", "watch competitor". Требует Firecrawl или Apify ключ.
---

Вызывает n8n workflow `competitor-monitor`. Возвращает markdown-snapshot конкурента, Sistem сохраняет в `memory_project`. При повторном вызове — diff с прошлым снимком.
