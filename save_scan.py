"""Find most recently modified compatible CS3 Windows save without altering files."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Iterable

from cs3_save import CS3Save, SAVE_SIZE, SaveFormatError

SAVE_NAME = re.compile(r'^save\d{3,4}\.dat$', re.IGNORECASE)


@dataclass(frozen=True)
class SaveMatch:
    path: Path
    modified_ns: int
    save: CS3Save


def save_directories(last_directory: str | Path | None = None,
                     home: Path | None = None) -> list[Path]:
    """Known PC CS3 save folder and a user-chosen folder, with no broad disk search."""
    home = Path(home) if home is not None else Path(os.environ.get('USERPROFILE') or Path.home())
    choices = [home / 'Saved Games' / 'FALCOM' / 'ed8_psv3']
    if last_directory:
        choices.append(Path(last_directory).expanduser())
    if os.environ.get('SAVEDGAMES'):
        choices.append(Path(os.environ['SAVEDGAMES']) / 'FALCOM' / 'ed8_psv3')
    # Desktop users may have a redirected Saved Games path configured in registry.
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            value, _ = winreg.QueryValueEx(key, '{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}')
            if isinstance(value, str) and value:
                choices.append(Path(os.path.expandvars(value)) / 'FALCOM' / 'ed8_psv3')
    except (ImportError, OSError):
        pass
    return list(dict.fromkeys(p for p in choices if p.is_dir()))


def newest_compatible_save(directories: Iterable[Path]) -> tuple[SaveMatch | None, list[str]]:
    """Try saves newest-first, rejecting unsupported/corrupt files.

    A changed mtime between stat/read is detected; the game could be still
    writing. There is no silent fallback to invalid files.
    """
    candidates: list[tuple[int, Path]] = []
    warnings = []
    visited = set()
    for folder in directories:
        folder = Path(folder)
        try:
            for p in folder.iterdir():
                if not SAVE_NAME.fullmatch(p.name) or not p.is_file():
                    continue
                try:
                    info = p.stat()
                    key = str(p.resolve()).casefold()
                    if key not in visited:
                        candidates.append((info.st_mtime_ns, p))
                        visited.add(key)
                except OSError:
                    continue
        except OSError as exc:
            warnings.append(f'Не удалось открыть папку {folder}: {exc}')
    for mtime_ns, p in sorted(candidates, key=lambda v: (v[0], str(v[1]).casefold()), reverse=True):
        try:
            info = p.stat()
            if info.st_size != SAVE_SIZE or info.st_mtime_ns != mtime_ns:
                warnings.append(f'{p.name}: несовместимый размер или файл обновляется')
                continue
            with p.open('rb') as stream:payload=stream.read(SAVE_SIZE+1)
            if p.stat().st_mtime_ns != mtime_ns:
                warnings.append(f'{p.name}: файл изменился во время чтения')
                continue
            save = CS3Save(payload)
            return SaveMatch(p.resolve(), mtime_ns, save), warnings
        except (OSError, ValueError, SaveFormatError) as exc:
            warnings.append(f'{p.name}: {exc}')
    return None, warnings
