"""Идемпотентный bootstrap: seed-юзер Тараса, дефолтные скиллы, дефолтный VPS bridge."""
from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sistem.models import BridgeVpsHost, Skill, Subscription, User
from sistem.security import hash_password

log = logging.getLogger("sistem.bootstrap")


DEFAULT_SKILLS = [
    # sistem-power-pack (уже готовые)
    ("marketing-audit",   "cowork:sistem-power-pack:marketing-audit",   "Быстрый маркетинг-аудит локального бизнеса"),
    ("site-landing",      "cowork:sistem-power-pack:site-landing",      "Премиум-лендинг для локального бизнеса"),
    ("itv-deal-card",     "cowork:sistem-power-pack:itv-deal-card",     "Карточка авто-сделки на импорт Германия→Испания"),
    ("content-reels",     "cowork:sistem-power-pack:content-reels",     "Конвейер коротких видео/рилсов"),
    ("lead-outreach",     "cowork:sistem-power-pack:lead-outreach",     "Лидген + холодный аутрич"),
    ("sales-funnel",      "cowork:sistem-power-pack:sales-funnel",      "Воронка продаж и прогрев"),
    ("reels-rewrite",     "cowork:sistem-power-pack:reels-rewrite",     "Рерайт залетевших рилсов под нашу нишу"),
    # taras-toolkit
    ("aeat-spanish-tax",            "cowork:taras-toolkit:aeat-spanish-tax",            "Испанские налоги AEAT"),
    ("content-translator",          "cowork:taras-toolkit:content-translator-ru-es-de", "RU/ES/DE локализация"),
    ("higgsfield-prompt",           "cowork:taras-toolkit:higgsfield-prompt",           "Промпты для Higgsfield"),
    ("itv-dealer-followup",         "cowork:taras-toolkit:itv-dealer-followup",         "Дожим дилеров DE/ES"),
    ("watersports-content",         "cowork:taras-toolkit:watersports-content",         "Контент для проката SUP"),
    # web-studio
    ("web-studio-orchestrator",     "cowork:web-studio:web-studio-orchestrator",        "Оркестратор полного цикла сайта"),
    ("web-designer",                "cowork:web-studio:web-designer",                   "Веб-дизайн"),
    ("web-frontend",                "cowork:web-studio:web-frontend",                   "Фронтенд"),
    ("web-qa",                      "cowork:web-studio:web-qa",                         "QA перед деплоем"),
    ("web-seo-growth",              "cowork:web-studio:web-seo-growth",                 "SEO + growth"),
    ("brand-assets",                "cowork:web-studio:brand-assets",                   "Бренд-ассеты + логотипы"),
    ("site-analytics",              "cowork:web-studio:site-analytics",                 "GA4 + Clarity"),
    ("site-deploy",                 "cowork:web-studio:site-deploy",                    "Деплой сайтов"),
    ("site-ux-review",              "cowork:web-studio:site-ux-review",                 "UX-ревью сайта"),
    # ai-clerk и sourcing
    ("ai-clerk",                    "cowork:ai-clerk:ai-clerk",                         "Универсальный AI-outreach"),
    ("car-export-sourcing",         "cowork:car-export-sourcing:car-export-sourcing",   "Конвейер подбора авто (mobile.de)"),
    # новые (Sprint 6)
    ("content-distribution",        "sistem:content-distribution",                       "Пост в N каналов проекта через Postiz"),
    ("competitor-watch",            "sistem:competitor-watch",                           "Мониторинг конкурентов (Firecrawl/Apify когда есть ключи)"),
    ("kpi-report",                  "sistem:kpi-report",                                 "KPI-отчёт по проекту"),
    # sistem-power-pack v0.3 (обновлено 2026-07-01)
    ("booking-agent",               "cowork:sistem-power-pack:booking-agent",            "AI-агент записи для сервисного бизнеса"),
    ("connector-setup",             "cowork:sistem-power-pack:connector-setup",          "Подключение remote-MCP-коннекторов в Cowork"),
    ("deep-research-runner",        "cowork:sistem-power-pack:deep-research-runner",     "Структурный ресёрч с проверкой фактов"),
    ("niche-comment-miner",         "cowork:sistem-power-pack:niche-comment-miner",      "Майнинг болей ниши из комментариев"),
    ("premium-design-checklist",    "cowork:sistem-power-pack:premium-design-checklist", "Ревизор премиум-вида, анти AI-slop"),
    ("retainer-agency",             "cowork:sistem-power-pack:retainer-agency",          "GTM-плейбук агентства на ретейнерах"),
    ("self-improve-loop",           "cowork:sistem-power-pack:self-improve-loop",        "Петля самоулучшения A/B гипотез"),
    ("sell-sites-localbiz",         "cowork:sistem-power-pack:sell-sites-localbiz",      "Плейбук продажи лендингов локалбизу"),
    ("unit-economics",              "cowork:sistem-power-pack:unit-economics",           "Юнит-экономика сделки (не только авто)"),
]


async def bootstrap(session: AsyncSession) -> None:
    # 1. Тарас
    email = "sullenlar4@gmail.com"
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        pw = os.getenv("SISTEM_BOOTSTRAP_PASSWORD", "change-me-on-first-login")
        user = User(email=email, password_hash=hash_password(pw), display_name="Тарас", role="owner", locale="ru")
        session.add(user)
        await session.flush()
        log.info("Bootstrap: created user %s", email)
    elif user.password_hash == "BOOTSTRAP_ME":
        pw = os.getenv("SISTEM_BOOTSTRAP_PASSWORD", "change-me-on-first-login")
        user.password_hash = hash_password(pw)
        log.info("Bootstrap: reset placeholder password for %s", email)

    # 2. Подписка (заглушка)
    sub = (await session.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one_or_none()
    if sub is None:
        session.add(Subscription(user_id=user.id, plan="personal", status="active"))

    # 3. Дефолтный VPS bridge (globria)
    bh = (
        await session.execute(
            select(BridgeVpsHost).where(
                BridgeVpsHost.user_id == user.id, BridgeVpsHost.host == "152.53.231.15"
            )
        )
    ).scalar_one_or_none()
    if bh is None:
        session.add(
            BridgeVpsHost(
                user_id=user.id,
                host="152.53.231.15",
                ssh_user="root",
                ssh_key_ref="/opt/sistem/secrets/id_ed25519",
                allow_cmds=[
                    r"^df -h$",
                    r"^free -h$",
                    r"^uptime$",
                    r"^docker ps.*$",
                    r"^systemctl status .+$",
                    r"^tail -n \d+ /var/log/.+$",
                ],
                enabled=True,
            )
        )

    # 4. Дефолтные скиллы
    existing_names = {
        r[0] for r in (await session.execute(select(Skill.name))).all()
    }
    for name, handler, desc in DEFAULT_SKILLS:
        if name not in existing_names:
            session.add(Skill(name=name, handler=handler, description=desc, enabled=True))

    await session.commit()
    log.info("Bootstrap complete")
