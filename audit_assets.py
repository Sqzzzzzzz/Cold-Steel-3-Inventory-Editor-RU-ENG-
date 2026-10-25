"""Non-destructive audit of item artwork availability and language catalog coverage.

Usage: python audit_assets.py [--catalog CATALOG.json] [--cache DIRECTORY]
The tool does not download or modify anything.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from catalog_core import load_catalog_json
from catalog_visibility import is_visible_item
from game_icons import (icon_cache_dir, GAME_ICON_FILES, EXACT_ITEM_ICON_FILES,
                        MASTER_QUARTZ_FILES, OFFICIAL_SPECIAL_ICONS,
                        special_local_icon_key, icon_key, validate_file)


def audit(catalog_path: Path, cache_path: Path):
    catalog = load_catalog_json(catalog_path)
    wanted, missing = Counter(), Counter()
    for item_id, item in catalog.items():
        if not is_visible_item(item):
            continue
        special_key = special_local_icon_key(item_id, item)
        filename = (EXACT_ITEM_ICON_FILES.get(item_id)
                    or OFFICIAL_SPECIAL_ICONS.get(special_key)
                    or MASTER_QUARTZ_FILES.get(item_id)
                    or GAME_ICON_FILES.get(icon_key(item,item_id))
                    or GAME_ICON_FILES.get(item.get('category','other')))
        if not filename:
            continue
        wanted[filename] += 1
        if not validate_file(cache_path/filename):
            missing[filename] += 1
    return sum(wanted.values()), wanted, missing


def main():
    parser = argparse.ArgumentParser(description='Audit cached Cold Steel III icon files')
    parser.add_argument('--catalog', type=Path, default=Path(__file__).parent/'catalog_builtin.json')
    parser.add_argument('--cache', type=Path, default=icon_cache_dir())
    args = parser.parse_args()
    if not args.catalog.is_file():
        parser.error('No item catalog found. Supply --catalog path from your game import.')
    matched, wanted, missing = audit(args.catalog,args.cache)
    print(f'Item entries checked: {matched}; unique filenames required: {len(wanted)}; missing: {len(missing)}')
    for filename, count in sorted(missing.items()):
        print(f'  MISSING {filename} — used by {count} item(s)')
    if missing:
        print('Open the editor and use Tools → Download original icons to attempt to fetch missing artwork.')
    else:
        print('All referenced icon PNGs are present and structurally valid. This does not prove pixel-level equivalence with the installed game.')

if __name__ == '__main__':
    main()
