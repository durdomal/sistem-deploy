"""Smoke: Skill Resolver v0.6 — чистая логика, без зависимостей и БД.

Гоняется standalone: `python app/tests/smoke_resolver.py` из корня репо.
Покрывает rule-матчинг (вкл. расширения v0.6), niche auto-switch, explicit
project=, project-hint из текста и fallback. Exit 1 при любом провале.
"""
from __future__ import annotations
import sys
from pathlib import Path

# stdout в utf-8, чтобы вывод кириллицы не падал в cp1251-консоли Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "app"))

from sistem.services.skill_resolver import resolve  # noqa: E402

fails = 0


def check(cond: bool, label: str) -> None:
    global fails
    if cond:
        print(f"OK  {label}")
    else:
        fails += 1
        print(f"XX  {label}")


# ── 1. rule-матчинг (включая новые паттерны v0.6) ──────────────
RULE_CASES = {
    "сделай пост про SUP": "content-reels",          # v0.6: "пост про"
    "напиши пост для инсты": "content-reels",         # v0.6: "напиши пост"
    "сделай рилс про прокат": "content-reels",
    "посчитай сделку по mobile.de": "itv-deal-card",  # v0.6: "посчитай сделку" + "mobile.de"
    "оцени сделку": "itv-deal-card",                  # v0.6: "оцени ... сделку"
    "карточка сделки": "itv-deal-card",
    "нужны лиды": "lead-outreach",                    # v0.6
    "найди лиды в Дении": "lead-outreach",            # v0.6
    "сделай аудит бизнеса": "marketing-audit",        # v0.6: аудит\\w*
    "маркетинг-аудитом займись": "marketing-audit",
    "сделай воронку продаж": "sales-funnel",
    "выкати сайт": "site-deploy",
    "modelo 303": "aeat-spanish-tax",
}
for text, expected in RULE_CASES.items():
    r = resolve(text)
    check(r.skill == expected, f"rule {text!r} -> {r.skill} (exp {expected}, rule={r.matched_rule})")

# ── 2. niche auto-switch (v0.6 _NICHE_HINTS) ───────────────────
KP = [
    {"slug": "itv-cb", "name": "ITV Costa Blanca", "niche": "car-import-sourcing"},
    {"slug": "wcb", "name": "Watersports", "niche": "sup-rental"},
    {"slug": "glob", "name": "Globria", "niche": "b2b-leadgen"},
]
NICHE_CASES = {
    "нужен импорт авто из Германии": "itv-cb",
    "прокат сап досок на лето": "wcb",
    "запусти аутрич jarvis": "glob",
}
for text, expected in NICHE_CASES.items():
    r = resolve(text, known_projects=KP)
    check(r.project_id == expected, f"niche {text!r} -> {r.project_id} (exp {expected})")

# ── 3. explicit project= перебивает авто-свитч ─────────────────
r = resolve("сделай пост project=wcb", known_projects=KP)
check(r.project_id == "wcb" and r.skill == "content-reels", "explicit project= override")

# ── 4. project-hint из текста ("для проекта X") ────────────────
r = resolve("сделай аудит для проекта itv-cb")
check(r.project_id == "itv-cb", "project hint 'для проекта itv-cb'")

# ── 5. fallback при отсутствии совпадений ──────────────────────
r = resolve("абракадабра без ключевых слов")
check(r.matched_rule == "fallback" and r.confidence < 0.5, "fallback low-confidence")

print()
if fails:
    print(f"=== resolver smoke: FAIL ({fails}) ===")
    sys.exit(1)
print("=== resolver smoke: PASS ===")
