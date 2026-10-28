"""Presentation-only hiding of game-internal entries, never modifying save data.

Only exact, corroborated status markers or known game IDs are used.  In
particular, an empty-looking description is *not* proof that an item is unused:
sepith and many legitimate quartz have `◆` descriptions in the source table.
"""
from __future__ import annotations
import re

# Seven-Element Sepith is a sepith-table entry, not a supported inventory stack.
# Keep existing save entries readable and removable; block new additions only.
NON_INVENTORY_ITEM_IDS = frozenset((249,))

_HIDDEN_DESCRIPTION = re.compile(
    r'^\s*[◆◇\s]*'
    r'(?:не\s+(?:отображается|появляется)\s+в\s+списке|'
    r'(?:not\s+(?:displayed|shown|listed)|does\s+not\s+appear|doesn[\x27’]t\s+appear)\s+(?:in|on)\s+(?:the\s+)?(?:item\s+)?list)'
    r'[.!\s]*$', re.IGNORECASE,
)


def is_unused_name(name: str) -> bool:
    normalized = name.strip().lstrip('◆◇■▪•★☆✦✧♦♢ \t').casefold()
    return bool(re.match(r'^unused(?:\b|$)', normalized))


def is_reserved_fish_placeholder(item: dict) -> bool:
    try:
        item_id = int(item.get('id', -1))
    except (ValueError, TypeError):
        return False
    return (2125 <= item_id <= 2129
            and str(item.get('name', '')).strip().casefold() in ('резерв', 'reserve')
            and str(item.get('description', '')).strip() == '◆')


def is_internal_list_entry(item: dict) -> bool:
    """Records explicitly marked by the game as not appearing in item lists."""
    return bool(_HIDDEN_DESCRIPTION.fullmatch(str(item.get('description', ''))))


def is_visible_item(item: dict) -> bool:
    return not ((type(item.get('id')) is int and item['id'] in NON_INVENTORY_ITEM_IDS)
                or is_unused_name(str(item.get('name', '')))
                or is_reserved_fish_placeholder(item)
                or is_internal_list_entry(item))
