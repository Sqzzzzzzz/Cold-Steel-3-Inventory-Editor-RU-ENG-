"""Resolve authentic CS3 assets. Missing art stays missing; nothing is drawn."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from catalog_core import resource_path
from categories import category_of
from game_icons import (
    GAME_ICON_FILES, MASTER_QUARTZ_FILES, EXACT_ITEM_ICON_FILES,
    OFFICIAL_SPECIAL_ICONS, icon_key, special_local_icon_key,
    icon_cache_dir, validate_file,
)


@dataclass(frozen=True)
class OriginalIcon:
    path: Path
    match: str  # item or family; never mislabel a family icon as unique art.
    verified: bool = True


@lru_cache(maxsize=1)
def _asset_hashes():
    try:
        data=json.loads(resource_path('icons/original/sources.json').read_text('utf8'))
        return {r['file']:r['sha256'] for r in data['files'] if isinstance(r,dict) and 'file' in r and 'sha256' in r}
    except (OSError,ValueError,KeyError,TypeError):return {}


@lru_cache(maxsize=512)
def _verified_asset(path,mtime_ns,size):
    path=Path(path)
    if not validate_file(path):return False
    expected=_asset_hashes().get(path.name)
    return bool(expected and hashlib.sha256(path.read_bytes()).hexdigest()==expected)


def verified_asset(path):
    try:
        info=path.stat()
        return _verified_asset(str(path),info.st_mtime_ns,info.st_size)
    except OSError:return False


def original_icon_for_item(item_id,record,*,bundled=None,cache=None,manual=None):
    bundled=Path(bundled) if bundled is not None else resource_path('icons/original')
    cache=Path(cache) if cache is not None else icon_cache_dir()
    manual=Path(manual) if manual is not None else resource_path('icons')
    for path in (manual/'by_id'/f'{item_id}.png',manual/f'{item_id}.png',cache/'by_id'/f'{item_id}.png'):
        if validate_file(path):return OriginalIcon(path,'item',False)
    exact=[]
    if item_id in EXACT_ITEM_ICON_FILES and category_of(record)=='material':exact.append(EXACT_ITEM_ICON_FILES[item_id])
    if category_of(record)=='quartz_master' and item_id in MASTER_QUARTZ_FILES:
        exact.append(MASTER_QUARTZ_FILES[item_id])
    for name in exact:
        for root in (bundled,cache):
            path=root/name
            if verified_asset(path):return OriginalIcon(path,'item')
    key=special_local_icon_key(item_id,record)
    names=[OFFICIAL_SPECIAL_ICONS.get(key),GAME_ICON_FILES.get(icon_key(record,item_id))]
    for name in dict.fromkeys(n for n in names if n):
        for root in (bundled,cache):
            path=root/name
            if verified_asset(path):return OriginalIcon(path,'family')
    return None
