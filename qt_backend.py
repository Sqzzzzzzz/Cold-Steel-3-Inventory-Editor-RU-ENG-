"""Pure-Python Qt front-end controller for CS3 inventory edits.

Keep save IO and catalog logic separate from PySide6. All writes are verified,
atomic and guarded against external modification of the opened save.
No original game data is bundled in the public source distribution.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
import csv
import hashlib
import io
import os
from pathlib import Path
import shutil
import tempfile

from beta_config import seed_beta_profile
from catalog_core import load_catalog_json, save_catalog_json, user_catalog_path, parse_item_tbl, clear_codes
from catalog_locale import catalog_locale, english_catalog, CYRILLIC
from catalog_visibility import is_visible_item, NON_INVENTORY_ITEM_IDS
from cs3_save import CS3Save, get_diff_summary
from dlc_translation import KNOWN_RUSSIAN_DLC
from game_scan import config_dir, find_game_install, load_settings, save_settings, scan_game_tables
from save_scan import newest_compatible_save, save_directories
from quartz_details import generated_help


class EditorCore:
    def __init__(self):
        self.persistence_warning = ''
        try:seed_beta_profile()
        except OSError as exc:self.persistence_warning=str(exc)
        self.settings = load_settings()
        self.language = self.settings.get('language', 'ru')
        self.favorites = {int(x) for x in self.settings.get('favorites', []) if str(x).isdigit()}
        self.recent = [int(x) for x in self.settings.get('recents', []) if str(x).isdigit()][:24]
        self.source: Path | None = None
        self.save: CS3Save | None = None
        self.undo_stack: deque[bytes] = deque(maxlen=20)
        self.base = self._read_catalog(config_dir() / 'catalog_scanned.json')
        self.english = self._read_catalog(config_dir() / 'catalog_english.json')
        if self.english and not english_catalog(self.english):self.english={}
        self.overrides = self._read_catalog(user_catalog_path())
        self.catalog: dict[int,dict] = {}
        self.rebuild_catalog()
        self.last_scan = None

    @staticmethod
    def _read_catalog(path):
        try: return load_catalog_json(path)
        except (OSError, ValueError, KeyError): return {}

    def _save_preferences(self):
        # A failed preference write must not turn a successful in-memory edit
        # or a successfully opened save into an apparent failed operation.
        try:
            save_settings(self.settings)
            self.persistence_warning=''
        except OSError as exc:self.persistence_warning=str(exc)

    def rebuild_catalog(self):
        # Older localized caches have no per-record locale. Detect their base
        # language once, rather than rescanning the whole catalog for every row.
        self._base_locale = catalog_locale(self.base)
        self.catalog = {i: dict(v) for i,v in self.base.items()}
        for i,v in self.overrides.items():
            self.catalog[i] = {**self.catalog.get(i,{}), **v}
        for i,v in KNOWN_RUSSIAN_DLC.items():
            if i in self.catalog and i not in self.overrides:
                self.catalog[i] = {**self.catalog[i], **v}
        # English fallback is always visible, but clearly marked when RU isn't present.
        for i,v in self.english.items():
            self.catalog.setdefault(i,dict(v))

    def set_language(self, language: str):
        if language not in ('ru','en'): raise ValueError('Invalid language')
        self.language=language
        self.settings['language']=language
        self._save_preferences()

    def item_name(self, i: int):
        ru=self.catalog.get(i, {})
        en=self.english.get(i, {})
        if self.language=='en':
            text=en.get('name') or ru.get('name') or f'ID {i}'
            locale=ru.get('_locale') or ('ru' if CYRILLIC.search(text) else 'unknown')
            if not en.get('name') and locale in ('ru','fr'):return '['+locale.upper()+'] '+text
            return text
        text=ru.get('name') or en.get('name') or f'ID {i}'
        if i not in self.overrides and ru.get('name') == en.get('name') and ru.get('name') and not any('А'<=c<='я' for c in text):
            # Names such as HP 1 may legitimately be identical in Russian and English;
            # an explicit locale tag on installed packs takes precedence.
            locale=ru.get('_locale') or (self._base_locale if i in self.base else 'unknown')
            if locale!='ru':
                return '[EN] '+text
        return text

    def description(self,i:int):
        ru=self.catalog.get(i, {})
        en=self.english.get(i,{})
        if self.language=='en':
            if en.get('description'):return en['description']
            text=ru.get('description') or ''
            locale=ru.get('_locale') or ('ru' if CYRILLIC.search(text) else 'unknown')
            return ('['+locale.upper()+']\n'+text) if text and locale in ('ru','fr') else text
        return ru.get('description') or en.get('description') or ''

    def details_text(self,i:int):
        if i in NON_INVENTORY_ITEM_IDS:
            return ('Эта запись из таблицы сепита не поддерживается как обычный предмет инвентаря. '
                    'Здесь можно удалить ранее добавленную запись. Счётчики ресурсов эта операция не изменяет.'
                    if self.language=='ru' else
                    'This sepith table entry is not supported as a regular inventory item. '
                    'An existing entry can be removed here. Resource balances are not changed by this operation.')
        text=clear_codes(self.description(i)).strip()
        if text not in ('','◆','◇','[RU]\n◆','[FR]\n◆'):return text
        localized=self.english.get(i,{}) if self.language=='en' else self.catalog.get(i,{})
        supplemental=generated_help(localized,self.language)
        if supplemental:return clear_codes(supplemental)
        # The game builds stat-only help from native ItemData fields. ◆ is a
        # placeholder, not proof that a legitimate item has no characteristics.
        stats=self.catalog.get(i,{}).get('stats',{})
        if stats:return '\n'.join(f'{key} {value:+d}' for key,value in stats.items())
        return 'Описание отсутствует в загруженном каталоге.' if self.language=='ru' else 'No description is available in the loaded catalog.'

    def import_english_catalog(self,path):
        path=Path(path)
        records=load_catalog_json(path) if path.suffix.lower()=='.json' else parse_item_tbl(path)
        if not english_catalog(records):
            raise ValueError('Select an original English catalog. This file contains Russian or another language.')
        records={i:{**{k:v for k,v in self.catalog.get(i,{}).items()
                        if not k.startswith('generated_description')},**r,'_locale':'en'} for i,r in records.items()}
        # A base-game table must not erase previously imported DLC translations.
        records={**self.english,**records}
        save_catalog_json(config_dir()/'catalog_english.json',records)
        self.english=records
        self.rebuild_catalog()
        return len(records)

    def visible(self):
        return {i:record for i,record in self.catalog.items() if is_visible_item(record)}

    def scan_game(self, path: Path|None=None):
        root=Path(path) if path is not None else find_game_install(self.settings.get('game_root',''))
        if root is None: raise FileNotFoundError('Cold Steel III installation not found')
        result=scan_game_tables(root)
        return self.apply_scan_result(result)

    def apply_scan_result(self,result):
        if not result.files: raise ValueError('No readable item tables found')
        root=result.root
        detected_locale=catalog_locale(result.items)
        new_base={i:dict(v) for i,v in self.base.items()}
        for i,record in result.items.items():
            prior=new_base.get(i,{})
            current=dict(record)
            current.setdefault('_locale',detected_locale)
            old_name=str(prior.get('name',''))
            # An original English scan must not erase an existing localized RU entry.
            prior_locale=prior.get('_locale') or self._base_locale
            if (old_name and (prior_locale=='ru' or CYRILLIC.search(old_name))
                    and current['_locale']=='en'):
                current['name']=prior['name']
                current['description']=prior.get('description','')
                current['_locale']='ru'
            new_base[i]={**prior,**current}
        # Restore verified custom Russian names rather than erase them on scan.
        save_catalog_json(config_dir()/'catalog_scanned.json',new_base)
        english_updates={i:record for i,record in result.items.items()
                         if record.get('_locale',detected_locale)=='en'}
        new_english={**self.english,**english_updates}
        if english_updates:save_catalog_json(config_dir()/'catalog_english.json',new_english)
        self.base=new_base
        self.english=new_english
        self.rebuild_catalog()
        self.settings['game_root']=str(root)
        self._save_preferences()
        self.last_scan=result
        return result

    def latest(self):
        match,warnings=newest_compatible_save(save_directories(self.settings.get('save_directory')))
        if match is None: raise FileNotFoundError('No compatible saveXXX.dat found. '+'; '.join(warnings[:2]))
        self._accept_save(match.path,match.save)
        return match.path

    def open_file(self,path):
        path=Path(path).expanduser().resolve()
        save=CS3Save.from_file(path)
        self._accept_save(path,save)
        return path

    def _accept_save(self,path,save):
        self.source=Path(path)
        self.save=save
        self.undo_stack.clear()
        self.settings['save_directory']=str(self.source.parent)
        self._save_preferences()

    def quantity(self,item_id):
        return self.save.get_quantity(item_id) if self.save else 0

    def change(self,changes:dict[int,int]):
        if self.save is None: raise RuntimeError('Open a compatible save first')
        before=self.save.bytes()
        self.save.set_quantities(changes)
        if self.save.bytes()!=before:
            self.undo_stack.append(before)
            for item_id in changes:
                if item_id in self.recent:self.recent.remove(item_id)
                self.recent.insert(0,item_id)
            self.recent=self.recent[:24]
            self.persist_lists()
        return self.save.changed

    def undo(self):
        if not self.save or not self.undo_stack:return False
        snapshot=self.undo_stack.pop()
        # CS3Save validates the entire restored structure.
        CS3Save(snapshot)
        self.save._data=bytearray(snapshot)
        return True

    def reset(self):
        if not self.save:return
        self.save.reset()
        self.undo_stack.clear()

    def persist_lists(self):
        self.settings['favorites']=sorted(self.favorites)
        self.settings['recents']=self.recent[:24]
        self._save_preferences()

    def toggle_favorite(self,item_id):
        if item_id in self.favorites:self.favorites.remove(item_id)
        else:self.favorites.add(item_id)
        self.persist_lists()

    def save_copy(self, destination):
        if self.save is None or self.source is None:raise RuntimeError('Save not loaded')
        destination=Path(destination).resolve()
        if destination == self.source:raise ValueError('Use overwrite with backup for source file')
        if destination.exists():raise FileExistsError('The destination exists. Pick a different filename.')
        payload=self.save.bytes()
        CS3Save(payload)
        self._atomic_write(destination,payload,replace=False)
        # Do not clear unsaved state: original opened save hasn't changed.
        return destination

    def export_csv(self, destination):
        if self.save is None or self.source is None:raise RuntimeError('No save loaded')
        destination=Path(destination).expanduser()
        if not destination.suffix:destination=destination.with_suffix('.csv')
        destination=destination.resolve()
        if (destination==self.source.resolve() or
                (destination.exists() and self.source.exists() and destination.samefile(self.source))):
            raise ValueError('CSV export cannot overwrite the opened save.')
        if destination.suffix.lower()!='.csv':
            raise ValueError('Choose a .csv file for inventory export.')
        stream=io.StringIO(newline='')
        writer=csv.writer(stream);writer.writerow(['ID','Name','Qty'])
        for entry in self.save.items():
            writer.writerow([entry.item_id,self.item_name(entry.item_id),entry.quantity])
        self._atomic_write(destination,stream.getvalue().encode('utf-8-sig'))
        return destination

    def overwrite_with_backup(self):
        if self.save is None or self.source is None:raise RuntimeError('Save not loaded')
        path=self.source
        current=CS3Save.from_file(path).bytes()
        if hashlib.sha256(current).hexdigest()!=self.save.original_sha256:
            raise RuntimeError('The original save was modified after loading; write cancelled')
        payload=self.save.bytes()
        CS3Save(payload)
        if payload==current:return None
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup=path.with_name(f'{path.stem}.{stamp}.bak')
        created=False
        try:
            with backup.open('xb') as out:
                created=True
                out.write(current); out.flush();os.fsync(out.fileno())
        except OSError:
            if created:
                try:backup.unlink()
                except OSError:pass
            raise
        self._atomic_write(path,payload,expected=current)
        self.save=CS3Save(payload)
        self.undo_stack.clear()
        return backup

    @staticmethod
    def _atomic_write(path:Path,payload:bytes,*,replace=True,expected=None):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='.cs3-save-',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as out:
                out.write(payload);out.flush();os.fsync(out.fileno())
            if expected is not None:
                with path.open('rb') as stream:actual=stream.read(len(expected)+1)
                if actual!=expected:
                    raise RuntimeError('The original save was modified after loading; write cancelled')
            if replace:os.replace(temp,path)
            elif os.name=='nt':os.rename(temp,path)  # Windows rename never replaces an existing destination.
            else:os.link(temp,path)  # Publish the complete temp file without a check/replace race.
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def compare(self,path):
        if self.save is None:raise RuntimeError('No save loaded')
        return get_diff_summary(self.save.bytes(),CS3Save.from_file(path).bytes())
