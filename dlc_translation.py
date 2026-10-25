"""Verified Russian DLC translations and tools to flag untranslated game text.

Do not guess RPG mechanics from arbitrary English sentences. Unresolved DLC
entries remain readable with an [EN] label until a Russian TBL/CSV is imported.
"""
from __future__ import annotations
import re

CYRILLIC = re.compile(r'[А-Яа-яЁё]')
LATIN_WORD = re.compile(r'[A-Za-z]{3,}')

# DLC 0010: official description confirms Aurelia-style swimwear for these three.
# Titles are intentionally not declared to be verbatim official Russian names.
# No original or derived game text bundled.
KNOWN_RUSSIAN_DLC = {}


def is_english_only(text: str) -> bool:
    return bool(LATIN_WORD.search(str(text))) and not bool(CYRILLIC.search(str(text)))


def missing_ru_entries(catalog: dict[int, dict], builtins: dict[int, dict]) -> list[dict]:
    """Identify names and descriptions which lack a known Russian source."""
    rows = []
    for item_id, item in sorted(catalog.items()):
        if item_id in KNOWN_RUSSIAN_DLC or item_id in builtins:
            continue
        name = str(item.get('name', ''))
        desc = str(item.get('description', ''))
        if is_english_only(name) or (desc and is_english_only(desc)):
            rows.append({'id': item_id, 'name': name, 'description': desc,
                         'missing_name': is_english_only(name),
                         'missing_description': is_english_only(desc)})
    return rows
