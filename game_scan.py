"""Discover CS3 installations, scan base/DLC TBL files, and persist UI settings.

This module has no tkinter dependencies and never modifies the game installation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from catalog_core import parse_item_tbl

APP_ID = '991270'
GAME_DIR_NAMES = (
    'The Legend of Heroes Trails of Cold Steel III',
    'The Legend of Heroes: Trails of Cold Steel III',
    'The Legend of Heroes - Trails of Cold Steel III',
    'Trails of Cold Steel III',
)


def config_dir() -> Path:
    appdata = os.environ.get('APPDATA')
    return (Path(appdata) if appdata else Path.home() / '.config') / 'CS3InventoryEditor'


def load_settings(path: Path | None = None) -> dict:
    target = path or config_dir() / 'settings.json'
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return {
                'theme': data.get('theme') if data.get('theme') in ('dark', 'light') else 'dark',
                'game_root': data.get('game_root') if isinstance(data.get('game_root'), str) else '',
                'save_directory': data.get('save_directory') if isinstance(data.get('save_directory'), str) else '',
                'auto_latest': data.get('auto_latest') is not False,
                'language': data.get('language') if data.get('language') in ('ru','en') else 'ru',
            }
    except (OSError, ValueError):
        pass
    return {'theme': 'dark', 'game_root': '', 'save_directory': '', 'auto_latest': True, 'language': 'ru'}


def save_settings(settings: dict, path: Path | None = None) -> None:
    target = path or config_dir() / 'settings.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.cs3-settings-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump({
                'theme': settings.get('theme', 'dark'),
                'game_root': settings.get('game_root', ''),
                'save_directory': settings.get('save_directory', ''),
                'auto_latest': settings.get('auto_latest', True),
                'language': settings.get('language', 'ru'),
            }, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_vdf(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig', errors='replace')


def steam_library_paths(steam_path: Path) -> list[Path]:
    """Steam's libraryfolders.vdf contains absolute paths, one per library entry.

    Both new format ('path' fields) and old numeric format are recognized.
    """
    folders = [steam_path]
    config = steam_path / 'steamapps' / 'libraryfolders.vdf'
    try:
        text = _read_vdf(config)
        paths = re.findall(r'"path"\s*"([^"]+)"', text, flags=re.I)
        if not paths:
            paths = re.findall(r'"\d+"\s*"([^"]+)"', text)
        for raw in paths:
            value = raw.replace('\\\\', '\\')  # Steam uses escaped backslashes
            lib = Path(value)
            if lib not in folders:
                folders.append(lib)
    except OSError:
        pass
    return folders


def possible_steam_roots() -> list[Path]:
    paths: list[Path] = []
    for env_name in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'ProgramFiles(x86)', 'ProgramFiles'):
        value = os.environ.get(env_name)
        if value:
            paths.append(Path(value) / 'Steam')
    for name in ('SteamPath', 'InstallPath'):
        try:
            import winreg  # type: ignore[import-not-found]
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                value, _ = winreg.QueryValueEx(key, name)
                paths.append(Path(value))
        except (ImportError, OSError):
            pass
    paths.extend([Path('C:/Program Files (x86)/Steam'), Path('C:/Program Files/Steam')])
    return list(dict.fromkeys(paths))


def is_game_root(root: str | Path) -> bool:
    path = Path(root)
    base = path / 'data' / 'text'
    if any((base / locale / fname).is_file()
           for locale in ('dat_en', 'dat')
           for fname in ('t_item_en.tbl', 't_item.tbl')):
        return True
    # DLC-only installs are also recognized, provided at least one valid file exists.
    dlc_root = path / 'data' / 'dlc' / 'text'
    try:
        return any((folder / locale / fname).is_file()
                   for folder in dlc_root.iterdir() if folder.is_dir()
                   for locale in ('dat_en', 'dat')
                   for fname in ('t_item.tbl', 't_item_en.tbl'))
    except OSError:
        return False


def find_game_install(configured: str | Path | None = None,
                      steam_roots: Iterable[Path] | None = None) -> Path | None:
    """Check saved selection, Steam manifests/libraries and conventional folders."""
    if configured:
        candidate = Path(configured).expanduser()
        if is_game_root(candidate):
            return candidate.resolve()
    tried: set[Path] = set()
    for steam in steam_roots if steam_roots is not None else possible_steam_roots():
        for lib in steam_library_paths(Path(steam)):
            if lib in tried:
                continue
            tried.add(lib)
            common = lib / 'steamapps' / 'common'
            manifest = lib / 'steamapps' / f'appmanifest_{APP_ID}.acf'
            try:
                match = re.search(r'"installdir"\s*"([^"]+)"', _read_vdf(manifest), re.I)
                if match:
                    path = common / match.group(1).replace('\\\\', '\\')
                    if is_game_root(path):
                        return path.resolve()
            except OSError:
                pass
            for name in GAME_DIR_NAMES:
                candidate = common / name
                if is_game_root(candidate):
                    return candidate.resolve()
    return None


def candidate_table_paths(root: Path) -> tuple[list[Path], list[Path]]:
    """Order matters: localized dat_en first, fallback dat; base before DLC.

    Returns (chosen base tables, chosen DLC tables). Each content folder yields
    at most one primary table, avoiding accidental overwrites by other locales.
    """
    root = Path(root)
    base_tables: list[Path] = []
    for locale in ('dat_en', 'dat'):
        folder = root / 'data' / 'text' / locale
        for name in ('t_item_en.tbl', 't_item.tbl'):
            p = folder / name
            if p.is_file():
                base_tables.append(p)
                break
        if base_tables:
            break
    dlc_tables: list[Path] = []
    dlc_root = root / 'data' / 'dlc' / 'text'
    try:
        packs = sorted((p for p in dlc_root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
    except OSError:
        packs = []
    for pack in packs:
        for locale in ('dat_en', 'dat'):
            for name in ('t_item_en.tbl', 't_item.tbl'):
                p = pack / locale / name
                if p.is_file():
                    dlc_tables.append(p)
                    break
            if dlc_tables and dlc_tables[-1].parent == pack / locale:
                break
    return base_tables, dlc_tables


@dataclass
class ScanResult:
    root: Path
    items: dict[int, dict] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    added_by_dlc: int = 0
    base_count: int = 0

    def summary(self) -> str:
        return (f'Найдено таблиц: {len(self.files)}\n'
                f'Основных предметов: {self.base_count}\n'
                f'Новых уникальных предметов DLC: {self.added_by_dlc}\n'
                f'Всего найдено ID: {len(self.items)}\n'
                f'Ошибок таблиц: {len(self.errors)}\n'
                f'Конфликтов ID: {len(self.conflicts)}')


def scan_game_tables(root: str | Path) -> ScanResult:
    root = Path(root).expanduser().resolve()
    if not is_game_root(root):
        raise ValueError('Выбранная папка не содержит таблиц предметов Cold Steel III. '
                         'Нужна папка с каталогом data (корневая папка игры).')
    result = ScanResult(root)
    base_files, dlc_files = candidate_table_paths(root)
    for p in base_files + dlc_files:
        try:
            if p.stat().st_size > 16 * 1024 * 1024:
                raise ValueError('Таблица слишком большая')
            parsed = parse_item_tbl(p)
        except (ValueError, OSError) as exc:
            result.errors.append(f'{p.relative_to(root)}: {exc}')
            continue
        result.files.append(p)
        if p in base_files:
            result.base_count += len(parsed)
        for item_id, item in parsed.items():
            if item_id in result.items:
                original = result.items[item_id]
                if original['name'] != item['name']:
                    result.conflicts.append(f'ID {item_id}: «{original["name"]}» / «{item["name"]}» ({p.relative_to(root)})')
                # Main game/base or first DLC wins; collisions must not silently rename items.
                continue
            result.items[item_id] = item
            if p in dlc_files:
                result.added_by_dlc += 1
    if not result.files:
        raise ValueError('Таблицы обнаружены, но прочитать ни одну не удалось:\n' + '\n'.join(result.errors[:5]))
    return result
