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
from game_icons import icon_cache_dir
from game_scan import config_dir
from original_item_icons import original_icon_for_item


def audit(catalog_path: Path, cache_path: Path):
    catalog = load_catalog_json(catalog_path)
    wanted, missing = Counter(), Counter()
    for item_id, item in catalog.items():
        if not is_visible_item(item):
            continue
        found=original_icon_for_item(item_id,item,cache=cache_path)
        filename=found.path.name if found else f'Unverified item ID {item_id}'
        wanted[filename] += 1
        if found is None or not found.verified:
            missing[filename] += 1
    return sum(wanted.values()), wanted, missing


def main():
    parser = argparse.ArgumentParser(description='Audit bundled and cached Cold Steel III item icons')
    parser.add_argument('--catalog', type=Path, default=config_dir()/'catalog_scanned.json')
    parser.add_argument('--cache', type=Path, default=icon_cache_dir())
    args = parser.parse_args()
    if not args.catalog.is_file():
        parser.error('No item catalog found. Supply --catalog path from your game import.')
    matched, wanted, missing = audit(args.catalog,args.cache)
    print(f'Item entries checked: {matched}; distinct mappings: {len(wanted)}; unavailable or unverified: {len(missing)}')
    for filename, count in sorted(missing.items()):
        print(f'  MISSING {filename} — used by {count} item(s)')
    if missing:
        print('Some item mappings are not verified. See DIAGNOSTICS_V793_RU.md and the per-ID mapping report.')
    else:
        print('All referenced icon PNGs are present and structurally valid. This does not prove pixel-level equivalence with the installed game.')

if __name__ == '__main__':
    main()
