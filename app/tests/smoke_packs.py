"""Smoke: все Project Pack валидны по JSON Schema (Sprint 7 — universality gate).

Гоняется: `python app/tests/smoke_packs.py` из корня репо.
Требует pyyaml + jsonschema (в app/requirements.txt). Exit 1 при любом провале.
"""
from __future__ import annotations
import sys, json, glob
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).resolve().parents[2]

import yaml            # noqa: E402
import jsonschema      # noqa: E402

schema = json.load(open(BASE / "schemas/project-pack.schema.json", encoding="utf-8"))
packs = sorted(glob.glob(str(BASE / "examples/*.pack.yaml")))
assert packs, "нет ни одного examples/*.pack.yaml"

fails = 0
for f in packs:
    d = yaml.safe_load(open(f, encoding="utf-8"))
    try:
        jsonschema.validate(d, schema)
        print(f"OK  {Path(f).name}  (project={d['project']['id']}, niche={d['project']['niche']})")
    except jsonschema.ValidationError as e:
        fails += 1
        print(f"XX  {Path(f).name}: {e.message} @ {list(e.path)}")

print()
if fails:
    print(f"=== packs smoke: FAIL ({fails}) ===")
    sys.exit(1)
print(f"=== packs smoke: PASS ({len(packs)} packs) ===")
