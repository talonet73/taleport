"""Writes docs/guide-{it,en,es}.md from the in-app guide (frontend/src/i18n/locales).

The app is the source of truth: run this after changing the guide texts.
    python docs/build_guide.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ["what", "sources", "daily", "ai", "reports", "privacy", "install", "problems"]

for lang in ("it", "en", "es"):
    guide = json.loads(
        (ROOT / "frontend" / "src" / "i18n" / "locales" / f"{lang}.json").read_text(encoding="utf-8")
    )["guide"]
    lines = [f"# TALeport — {guide['title']}", "", guide["subtitle"], ""]
    for key in SECTIONS:
        section = guide["sections"][key]
        lines += [f"## {section['title']}", "", *(f"- {item}" for item in section["items"]), ""]
    (ROOT / "docs" / f"guide-{lang}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"docs/guide-{lang}.md")
