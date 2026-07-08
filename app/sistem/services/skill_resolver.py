"""Skill Resolver v0.6 — rule-based + auto project switcher (zero-config для юзера)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Resolution:
    skill: str
    params: dict[str, Any]
    project_id: str | None
    confidence: float
    matched_rule: str


# rule → (regex_patterns, skill_name)
RULES: list[tuple[str, list[str], str]] = [
    ("kpi-report",         [r"(?i)\bkpi[- ]?(отч[её]т|report)\b", r"(?i)\bсколько (продаж|броней|лидов|подписч)"], "kpi-report"),
    ("content-reels",      [r"(?i)\bсделай (рилс|reel|видео)", r"(?i)\bсценарий рилса", r"(?i)\bкороткое видео", r"(?i)\b(сделай|напиши|сгенер\w+) пост\b", r"(?i)\bпост про\b"], "content-reels"),
    ("reels-rewrite",      [r"(?i)\bперепиши (рилс|видео)", r"(?i)\bрерайт (рилс|reel)"], "reels-rewrite"),
    ("content-distribution", [r"(?i)\bопубликуй\b", r"(?i)\bзапости\b", r"(?i)\bраспространи пост\b"], "content-distribution"),
    ("marketing-audit",    [r"(?i)\b(маркетинг[- ]?)?аудит\w*", r"(?i)\baudit (this|the) (business|site)"], "marketing-audit"),
    ("site-landing",       [r"(?i)\bсделай лендинг\b", r"(?i)\bсобери лендинг\b", r"(?i)\bpremium landing\b"], "site-landing"),
    ("itv-deal-card",      [r"(?i)\bкарточка сделки\b", r"(?i)\b(под|по)?считай (авто|машину|сделку)", r"(?i)\bоцени (авто|машину|сделку)", r"(?i)\bсделку по\b", r"(?i)\bmobile\.de\b"], "itv-deal-card"),
    ("lead-outreach",      [r"(?i)\bхолодный аутрич\b", r"(?i)\bнайди (клиентов|лиды)\b", r"(?i)\bcold outreach\b", r"(?i)\bнайд[ий] клиент", r"(?i)\bнужны лиды\b", r"(?i)\bнайди лиды\b"], "lead-outreach"),
    ("sales-funnel",       [r"(?i)\bворонк[аиу]\b", r"(?i)\bтрипваер\b", r"(?i)\bпрогрев\b"], "sales-funnel"),
    ("competitor-watch",   [r"(?i)\bмониторинг конкурент", r"(?i)\bwatch competitor"], "competitor-watch"),
    ("web-studio-rebuild", [r"(?i)\bпересобери сайт\b", r"(?i)\bпройди сайт командой\b", r"(?i)\brebuild the site\b"], "web-studio-orchestrator"),
    ("brand-assets",       [r"(?i)\bдобавь лого\b", r"(?i)\bстена логотип", r"(?i)\blogo wall\b"], "brand-assets"),
    ("web-qa",             [r"(?i)\bперед выкатом\b", r"(?i)\bпровер(ь|ка сайта)\b", r"(?i)\brun QA\b"], "web-qa"),
    ("site-deploy",        [r"(?i)\bвыкати\b", r"(?i)\bзадеплой\b", r"(?i)\bdeploy the site\b"], "site-deploy"),
    ("content-translator", [r"(?i)\bпереведи на (испанский|немецкий)", r"(?i)\btranslate to (spanish|german)"], "content-translator"),
    ("aeat-tax",           [r"(?i)\bmodelo\s*\d+\b", r"(?i)\bAEAT\b", r"(?i)\bналог(и)? (испани[ия])"], "aeat-spanish-tax"),
]


_PROJECT_HINT_RE = re.compile(r"(?:project\s*=\s*|для\s+проекта\s+)([a-z0-9][a-z0-9-]{0,47})", re.I)

# Ключевые слова свободного текста → niche проекта. Zero-config авто-свитч,
# когда юзер не называет проект напрямую («импорт авто» → car-import-sourcing).
_NICHE_HINTS: list[tuple[str, str]] = [
    (r"(?i)импорт авто|подбор авто|mobile\.de|сделку по|растаможк|matricul|car import", "car-import-sourcing"),
    (r"(?i)\bsup\b|\bсап\b|доск[аи]|прокат|каяк|paddle", "sup-rental"),
    (r"(?i)ресторан|меню|бронь стол|столик|covers|paella|бистро", "restaurant"),
    (r"(?i)\bлид[ыаов]?\b|leadgen|lead-gen|jarvis|аутрич|outreach|ретейнер", "b2b-leadgen"),
]


def _auto_project(text: str, known_projects: list[dict] | None) -> str | None:
    """Auto-switcher: ищет проект по slug/name/niche, затем по niche-ключам в тексте."""
    if not known_projects:
        return None
    t = text.lower()
    by_niche = {(p.get("niche") or "").lower(): p["slug"] for p in known_projects}
    # 1. slug
    for p in known_projects:
        slug = p["slug"].lower()
        if re.search(rf"\b{re.escape(slug)}\b", t):
            return p["slug"]
    # 2. name — слова длиной ≥5
    for p in known_projects:
        name = (p.get("name") or "").lower()
        for w in re.split(r"[\s\-_,]+", name):
            if len(w) >= 5 and w in t:
                return p["slug"]
    # 3. niche как подстрока
    for p in known_projects:
        niche = (p.get("niche") or "").lower()
        if niche and len(niche) >= 4 and niche in t:
            return p["slug"]
    # 4. niche по ключевым словам свободного текста
    for pat, niche in _NICHE_HINTS:
        if niche in by_niche and re.search(pat, text):
            return by_niche[niche]
    return None


def resolve(text: str, explicit_project: str | None = None,
            known_projects: list[dict] | None = None) -> Resolution:
    project_id = explicit_project
    if not project_id:
        m = _PROJECT_HINT_RE.search(text)
        if m:
            project_id = m.group(1).lower()
    if not project_id:
        project_id = _auto_project(text, known_projects)

    for rule_name, patterns, skill in RULES:
        for pat in patterns:
            if re.search(pat, text):
                return Resolution(
                    skill=skill, params={"text": text},
                    project_id=project_id, confidence=0.9,
                    matched_rule=rule_name,
                )

    return Resolution(
        skill="marketing-audit", params={"text": text, "fallback": True},
        project_id=project_id, confidence=0.2, matched_rule="fallback",
    )
