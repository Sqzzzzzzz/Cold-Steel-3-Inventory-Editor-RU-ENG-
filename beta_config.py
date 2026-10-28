"""Separate beta profile: read stable resources once, never write to stable profile.

The beta works from existing installed-game data but is safe to test alongside
v7.0.1. No save game files are copied or modified during migration.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil

BETA_FOLDER = 'CS3InventoryEditor_BETA'
STABLE_FOLDER = 'CS3InventoryEditor'
CATALOG_FILES = ('settings.json','catalog_scanned.json','catalog_english.json','catalog_overrides.json')
MAX_CATALOG = 12 * 1024 * 1024


def user_root() -> Path:
    return Path(os.environ['APPDATA']) if os.environ.get('APPDATA') else Path.home()/'.config'


def beta_dir() -> Path:
    return user_root()/BETA_FOLDER


def seed_beta_profile() -> Path:
    """One-time selective copy of known settings/cache files from stable profile."""
    stable=user_root()/STABLE_FOLDER
    beta=beta_dir()
    beta.mkdir(parents=True,exist_ok=True)
    for name in CATALOG_FILES:
        src=stable/name
        dst=beta/name
        if (not dst.exists() and src.is_file() and not src.is_symlink()
                and src.stat().st_size <= MAX_CATALOG):
            shutil.copy2(src,dst)
    old_icons=stable/'icons'/'original'
    new_icons=beta/'icons'/'original'
    if old_icons.is_dir():
        new_icons.mkdir(parents=True,exist_ok=True)
        for source in old_icons.glob('*.png'):
            dest=new_icons/source.name
            if not dest.exists() and source.is_file() and not source.is_symlink() and source.stat().st_size<=2*1024*1024:
                shutil.copy2(source,dest)
    return beta
