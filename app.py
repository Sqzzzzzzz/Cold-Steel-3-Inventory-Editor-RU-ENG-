"""Bilingual Windows GUI for safely preparing Trails of Cold Steel III inventory edits."""
from __future__ import annotations

import hashlib
import queue
import threading
import os
from pathlib import Path
import shutil
import tempfile
import tkinter as tk
from i18n import (ttk, messagebox, filedialog, tr, set_language,
                  LocalizedStringVar, EN)

from catalog_core import (clear_codes, load_catalog_json, load_external_catalog,
                          resource_path, save_catalog_json, user_catalog_path)
from cs3_save import CS3Save, SaveFormatError, get_diff_summary, MAX_QUANTITY
from categories import GROUPS, CATEGORY_NAMES, category_of, item_in_category
from catalog_visibility import is_visible_item
from game_icons import (icon_cache_dir, icon_file_for_item,
                        download_original_icons, import_original_icons, validate_file, ALL_ORIGINAL_FILES, MASTER_QUARTZ_FILES, special_local_icon_key, OFFICIAL_SPECIAL_ICONS)
from save_scan import save_directories, newest_compatible_save
from game_scan import (find_game_install, load_settings, save_settings,
                       scan_game_tables, config_dir)
from dlc_translation import KNOWN_RUSSIAN_DLC, is_english_only, missing_ru_entries
import csv

APP_NAME = 'Cold Steel III — Inventory Editor v7.0'


class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry('1450x870')
        self.minsize(1140, 710)
        self.save: CS3Save | None = None
        self.source: Path | None = None
        self.settings = load_settings()
        self.language = self.settings.get('language', 'ru')
        set_language(self.language)
        self.language_var = tk.StringVar(value='English' if self.language=='en' else 'Русский')
        # The personalized offline edition contains an English catalog parsed
        # from the owner's clean game tables. Public source releases deliberately
        # exclude it and rely on game scanning/import instead.
        try:
            english_builtin = load_catalog_json(resource_path('catalog_english.json'))
        except (OSError, ValueError, KeyError):
            english_builtin = {}
        try:
            english_cached = load_catalog_json(config_dir() / 'catalog_english.json')
        except (OSError, ValueError, KeyError):
            english_cached = {}
        # Official English data supersedes any stale cache entries for matching
        # IDs, while extra DLC IDs imported by the user remain available.
        self.english_catalog = {**english_cached, **english_builtin}
        try:
            self.builtin = load_catalog_json(resource_path('catalog_builtin.json'))
        except (OSError, ValueError, KeyError):
            self.builtin = {}  # source-only GitHub build: scan the user's local installation
        try:
            self.scanned_catalog = load_catalog_json(config_dir() / 'catalog_scanned.json')
        except (OSError, ValueError, KeyError):
            self.scanned_catalog = {}
        try:
            self.user_overrides = load_catalog_json(user_catalog_path())
        except (OSError, ValueError, KeyError):
            self.user_overrides = {}
        # Older versions cached English DLC entries only in the mixed-language
        # scan. Recover their original names for language switching on startup,
        # even when the game folder has moved or a new scan cannot complete.
        for item_id, record in self.scanned_catalog.items():
            if item_id not in self.english_catalog and is_english_only(record.get('name','')):
                self.english_catalog[item_id] = record.copy()
        self.catalog = {}
        self._rebuild_catalog()
        self._item_images = {}
        self._resolved_icon_paths = {}
        self._sort_state = {'catalog': ('name', False), 'inventory': ('slot', False)}
        self._search_jobs = {}
        self._startup_jobs = []
        self._scan_poll_job = None
        self._icon_poll_job = None
        self._icon_events = queue.Queue()
        self._icon_downloading = False
        self.icon_status = LocalizedStringVar(value=self._icon_status_text())
        self.theme_var = tk.StringVar(value=('Dark' if self.language=='en' else 'Тёмная') if self.settings['theme'] == 'dark' else ('Light' if self.language=='en' else 'Светлая'))
        self._scan_events = queue.Queue()
        self._scanning = False
        self.scan_info = LocalizedStringVar(value='Сканирование игры: ещё не выполнялось')
        self.style = ttk.Style(self)
        self.apply_theme(save=False)
        self.search_inv = tk.StringVar()
        self.search_all = tk.StringVar()
        self.only_missing = tk.BooleanVar(value=False)
        self.auto_latest = tk.BooleanVar(value=self.settings.get('auto_latest', True))
        self.active_category = 'all'
        self.save_line = LocalizedStringVar(value='Сохранение не открыто. Можно выбрать файл вручную.')
        self.item_var = tk.StringVar()
        self.qty_var = tk.StringVar(value='1')
        self.status = LocalizedStringVar(value='Выберите предмет из каталога; для редактирования откройте saveXXX.dat')
        self.catalog_status = LocalizedStringVar(value=f'Доступный каталог: {len(self.catalog)} предметов')
        self.tools_expanded = False
        self.selected_item = None
        self._history: list[bytes] = []
        self._make_ui()
        self.search_inv.trace_add('write', lambda *_: self._schedule_filter('inventory'))
        self.search_all.trace_add('write', lambda *_: self._schedule_filter('catalog'))
        self.only_missing.trace_add('write', lambda *_: self.refresh_catalog())
        self.refresh_catalog()
        # Start after the window opens. Scanning happens off the UI thread.
        self._startup_jobs.append(self.after(400, lambda: self.start_scan(manual=False)))
        # Original icons download to a local cache; network work never blocks Tk.
        self._startup_jobs.append(self.after(1500, lambda: self.start_icon_download(manual=False)))
        if self.auto_latest.get():
            self._startup_jobs.append(self.after(250, lambda: self.load_latest_save(manual=False)))
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.bind('<Control-o>', lambda _e: self.open_save())
        self.bind('<Control-f>', self.focus_catalog_search)
        self.bind('<F5>', lambda _e: self.load_latest_save(manual=True))
        self.bind('<Control-s>', lambda _e: self.save_copy())

    def _icon_status_text(self):
        cache=icon_cache_dir()
        available=sum(validate_file(cache/name) for name in ALL_ORIGINAL_FILES)
        total=len(ALL_ORIGINAL_FILES)
        master=sum(validate_file(cache/name) for name in set(MASTER_QUARTZ_FILES.values()))
        master_total=len(set(MASTER_QUARTZ_FILES.values()))
        return f'Оригинальные иконки: {available}/{total}  •  Мастер-кварцы: {master}/{master_total}'

    def start_icon_download(self, manual=True):
        if self._icon_downloading:
            return
        if not manual and all(validate_file(icon_cache_dir()/name)
                              for name in ALL_ORIGINAL_FILES):
            return
        self._icon_downloading = True
        self.icons_button.configure(state='disabled')
        self.icon_status.set('Загрузка игровых значков в кеш (редактор продолжает работать)…')

        def work():
            try:
                count,errors=download_original_icons()
                self._icon_events.put(('done',count,errors,manual))
            except (OSError,ValueError,KeyError) as exc:
                self._icon_events.put(('done',0,[str(exc)],manual))
        threading.Thread(target=work,name='CS3OriginalIconDownloader',daemon=True).start()
        self._icon_poll_job=self.after(120,self._check_icon_events)

    def _check_icon_events(self):
        self._icon_poll_job=None
        if not self.winfo_exists():return
        try:
            event,count,errors,manual=self._icon_events.get_nowait()
        except queue.Empty:
            if self._icon_downloading:
                self._icon_poll_job=self.after(120,self._check_icon_events)
            return
        self._icon_downloading=False
        self.icons_button.configure(state='normal')
        self._item_images.clear()
        self._resolved_icon_paths.clear()
        self.refresh_catalog()
        self.refresh_inventory()
        summary=self._icon_status_text()
        if errors:
            summary += f' Ошибок: {len(errors)}; можно повторить загрузку.'
            try:
                errlog=icon_cache_dir().parent/'icon_download_errors.txt'
                errlog.parent.mkdir(parents=True,exist_ok=True)
                errlog.write_text('\n'.join(errors), encoding='utf-8')
            except OSError:
                pass
        self.icon_status.set(summary)
        if manual:
            loaded=self.icon_status.get()
            if errors:
                messagebox.showwarning('Игровые значки', loaded+'\n\nОшибки загрузки: '
                    +str(len(errors))+'\n'+'\n'.join(errors[:5]))
            else:
                messagebox.showinfo('Игровые значки',loaded)

    def choose_icon_folder(self):
        folder=filedialog.askdirectory(title='Выберите папку с оригинальными PNG-иконками',
                                       mustexist=True)
        if not folder:
            return
        try:
            imported,invalid=import_original_icons(Path(folder))
            self._item_images.clear()
            self._resolved_icon_paths.clear()
            self.refresh_catalog()
            self.refresh_inventory()
            self.icon_status.set(self._icon_status_text())
            messagebox.showinfo('Импорт иконок',
                f'Импортировано файлов: {imported}\nПропущено повреждённых: {len(invalid)}\n'
                'Копии сохранены отдельно от файлов игры.')
        except (OSError,ValueError) as exc:
            messagebox.showerror('Импорт иконок',str(exc))

    def _rebuild_catalog(self):
        merged = {k: v.copy() for k, v in self.builtin.items()}
        for item_id, item in self.scanned_catalog.items():
            original = merged.get(item_id, {})
            updates = {k:v for k,v in item.items() if v or k == 'id'}
            # Never overwrite verified Russian base-game text with English
            # text from a mixed-language/DLC installation.
            if item_id in self.builtin and is_english_only(str(item.get('name', ''))):
                updates.pop('name', None)
                updates.pop('description', None)
            merged[item_id] = {**original, **updates}
        for item_id, item in self.user_overrides.items():
            original = merged.get(item_id, {})
            merged[item_id] = {**original, **{k:v for k,v in item.items() if v or k == 'id'}}
        # Store a separate English overlay without altering original source.
        for item_id, text in KNOWN_RUSSIAN_DLC.items():
            if item_id in merged and (item_id not in self.builtin) and (item_id not in self.user_overrides):
                merged[item_id] = {**merged[item_id], **text}
        self.catalog = merged
        if hasattr(self, '_item_images'):
            self._item_images.clear()
        if hasattr(self, '_resolved_icon_paths'):
            self._resolved_icon_paths.clear()

    def apply_theme(self, save=True):
        """Two complete, cohesive ttk palettes, including panels and native Text."""
        dark = self.theme_var.get() in ('Тёмная','Dark')
        p = ({'bg':'#101722','panel':'#1A2535','surface':'#202E40',
              'fg':'#F2F5FA','muted':'#A5B3C4','input':'#131F2D',
              'border':'#34465B','select':'#295A8C','button':'#29384B',
              'hover':'#354D66','disabled':'#8494A6','accent':'#367CC8',
              'accent_hover':'#4492E3','danger':'#BA6371','stripe':'#202D3D',
              'focus':'#74B8FF'} if dark else
             {'bg':'#F3F6FA','panel':'#FFFFFF','surface':'#EFF3F9',
              'fg':'#18283B','muted':'#52667D','input':'#FFFFFF',
              'border':'#D4DEEA','select':'#D7E8FF','button':'#EBF1F9',
              'hover':'#DDE9F9','disabled':'#8795A6','accent':'#1E66BA',
              'accent_hover':'#1454A4','danger':'#B84350','stripe':'#F5F8FC',
              'focus':'#075FBA'})
        self.style.theme_use('clam')
        self.configure(background=p['bg'])
        self.style.configure('.', font=('Segoe UI', 10), background=p['bg'], foreground=p['fg'])
        self.style.configure('TFrame', background=p['bg'])
        self.style.configure('App.TFrame', background=p['bg'])
        self.style.configure('Card.TFrame', background=p['panel'])
        self.style.configure('Header.TFrame', background=p['panel'])
        self.style.configure('TLabel', background=p['bg'], foreground=p['fg'])
        self.style.configure('Card.TLabel', background=p['panel'], foreground=p['fg'])
        self.style.configure('CardMuted.TLabel', background=p['panel'], foreground=p['muted'])
        self.style.configure('Title.TLabel', background=p['panel'], foreground=p['fg'], font=('Segoe UI Semibold', 15))
        self.style.configure('Section.TLabel', background=p['panel'], foreground=p['fg'], font=('Segoe UI Semibold', 11))
        self.style.configure('Info.TLabel', background=p['bg'], foreground=p['muted'])
        self.style.configure('TButton', background=p['button'], foreground=p['fg'],
                             bordercolor=p['border'], relief='flat', padding=(11,8),
                             focuscolor=p['focus'])
        self.style.map('TButton', background=[('disabled',p['surface']),('pressed',p['select']),('active',p['hover'])],
                       foreground=[('disabled',p['disabled'])])
        self.style.configure('Accent.TButton', background=p['accent'], foreground='#FFFFFF',
                             bordercolor=p['accent'], relief='flat', padding=(11,9))
        self.style.map('Accent.TButton', background=[('active',p['accent_hover']),('pressed',p['select'])],
                       foreground=[('disabled',p['disabled'])])
        self.style.configure('Danger.TButton', background=p['surface'], foreground=p['danger'],
                             bordercolor=p['border'], padding=(11,8), relief='flat')
        self.style.map('Danger.TButton', background=[('active',p['hover'])])
        for sty, parent_bg in (('TCheckbutton',p['bg']),('Card.TCheckbutton',p['panel'])):
            self.style.configure(sty, background=parent_bg, foreground=p['fg'])
            self.style.map(sty, background=[('active', parent_bg)],foreground=[('disabled',p['disabled'])])
        for widget in ('TEntry','TSpinbox','TCombobox'):
            self.style.configure(widget, fieldbackground=p['input'], background=p['input'],
                                 foreground=p['fg'], bordercolor=p['border'], arrowcolor=p['fg'],
                                 insertcolor=p['fg'], padding=6)
            self.style.map(widget, fieldbackground=[('readonly',p['input']),('disabled',p['surface'])],
                           foreground=[('readonly',p['fg']),('disabled',p['disabled'])],
                           selectbackground=[('focus',p['select'])])
        self.style.configure('TNotebook', background=p['bg'], borderwidth=0,
                             bordercolor=p['border'], lightcolor=p['border'],darkcolor=p['border'])
        self.style.configure('TNotebook.Tab', background=p['button'], foreground=p['fg'],
                             borderwidth=0, bordercolor=p['border'],
                             lightcolor=p['border'],darkcolor=p['border'],padding=(16,10))
        self.style.map('TNotebook.Tab', background=[('selected',p['panel']),('active',p['hover'])])
        for prefix in ('','Category.'):
            self.style.configure(prefix+'Treeview', background=p['panel'], foreground=p['fg'],
                                 fieldbackground=p['panel'], bordercolor=p['border'],
                                 borderwidth=0, lightcolor=p['border'],darkcolor=p['border'],rowheight=29)
            self.style.map(prefix+'Treeview', background=[('selected',p['select'])],
                           foreground=[('selected','#FFFFFF' if dark else p['fg'])])
        self.style.configure('Treeview.Heading', background=p['surface'], foreground=p['fg'],
                             bordercolor=p['border'], lightcolor=p['border'],darkcolor=p['border'],
                             relief='flat', padding=(7,8),
                             font=('Segoe UI Semibold',10))
        self.style.map('Treeview.Heading', background=[('active',p['hover'])])
        for name in ('TScrollbar','Vertical.TScrollbar','Horizontal.TScrollbar'):
            self.style.configure(name, background=p['button'], troughcolor=p['bg'],
                                 bordercolor=p['border'], arrowcolor=p['fg'])
        self.style.configure('TSeparator', background=p['border'])
        if hasattr(self, 'details'):
            self.details.configure(bg=p['input'],fg=p['fg'],insertbackground=p['fg'],
                                   highlightbackground=p['border'],selectbackground=p['select'],
                                   selectforeground='#FFFFFF' if dark else p['fg'])
        if hasattr(self,'tree'):
            for tree in (self.tree,self.all_tree):
                tree.tag_configure('stripe', background=p['stripe'])
        self._colors=p
        if save:
            self.settings['theme']='dark' if dark else 'light'
            try: save_settings(self.settings)
            except OSError as exc: self.scan_info.set(f'Не удалось запомнить тему: {exc}')

    def start_scan(self, manual=True, folder=None):
        if self._scanning:
            return
        self._scanning = True
        self.scan_info.set('Поиск файлов предметов в папке игры и DLC…')
        self.scan_button.configure(state='disabled')
        configured = str(folder) if folder else self.settings.get('game_root', '')

        def work():
            try:
                path = Path(folder) if folder else find_game_install(configured)
                if path is None:
                    self._scan_events.put(('missing', manual, None))
                    return
                scan = scan_game_tables(path)
                self._scan_events.put(('result', manual, scan))
            except (OSError, ValueError) as exc:
                self._scan_events.put(('error', manual, str(exc)))
        threading.Thread(target=work, name='CS3TableScanner', daemon=True).start()
        self._scan_poll_job=self.after(100, self._check_scan_events)

    def _check_scan_events(self):
        self._scan_poll_job=None
        if not self.winfo_exists():return
        try:
            event, manual, result = self._scan_events.get_nowait()
        except queue.Empty:
            if self._scanning:
                self._scan_poll_job=self.after(120, self._check_scan_events)
            return
        self._scanning = False
        self.scan_button.configure(state='normal')
        if event == 'missing':
            self.scan_info.set('Папка игры не найдена автоматически. Укажите её кнопкой «Папка игры…».')
            if manual:
                messagebox.showinfo('Поиск игры', 'Steam-установка не найдена. Нажмите «Папка игры…» '
                    'и выберите корневую папку Cold Steel III (где находится data).')
        elif event == 'error':
            self.scan_info.set('Не удалось прочитать таблицы; сохранённый каталог остался доступен.')
            if manual:
                messagebox.showerror('Сканирование', result)
        else:
            # If the user's installation is clean English, retain its exact
            # official text as a separate language catalog. Russian DLC mods
            # still populate the Russian working catalog as before.
            import re
            latin = sum(bool(re.search('[A-Za-z]{3,}',v['name'])) and not
                        re.search('[А-Яа-яЁё]',v['name']) for v in result.items.values())
            if latin >= max(20, int(len(result.items)*0.85)):
                # A clean English installation must populate the working catalog
                # in source-only builds, not merely the translation overlay.
                # In a Russian build do not overwrite its translated names.
                new_english = {**self.english_catalog, **result.items}
                try:
                    save_catalog_json(config_dir()/'catalog_english.json',new_english)
                except OSError as exc:
                    persistence_errors = [f'Не удалось сохранить английский каталог: {exc}']
                else:
                    persistence_errors = []
                self.english_catalog = new_english
                if not self.builtin:
                    self.scanned_catalog = result.items
                else:
                    self.scanned_catalog = {
                        **self.scanned_catalog,
                        **{k:v for k,v in result.items.items()
                           if k not in self.builtin and k not in self.scanned_catalog},
                    }
            else:
                persistence_errors = []
                self.scanned_catalog = result.items
                # Mixed-language games: preserve English DLC names by ID for
                # switching back to English, including known RU-localized DLC.
                english_dlc = {k:v for k,v in result.items.items()
                               if is_english_only(v.get('name',''))}
                if english_dlc:
                    self.english_catalog.update(english_dlc)
                    try:
                        save_catalog_json(config_dir()/'catalog_english.json',self.english_catalog)
                    except OSError as exc:
                        persistence_errors.append(f'Не удалось сохранить английский каталог: {exc}')
            self._rebuild_catalog()
            self.settings['game_root'] = str(result.root)
            try:
                save_catalog_json(config_dir() / 'catalog_scanned.json', self.scanned_catalog)
            except OSError as exc:
                persistence_errors.append(f'Не удалось сохранить каталог: {exc}')
            try:
                save_settings(self.settings)
            except OSError as exc:
                persistence_errors.append(f'Не удалось сохранить путь к игре: {exc}')
            self._populate_categories()
            self._refresh()
            self.scan_info.set(f'Сканировано таблиц: {len(result.files)}; '
                  f'из DLC добавлено: {result.added_by_dlc}; всего ID: {len(self.catalog)}'
                  + (' (есть ошибки)' if result.errors or persistence_errors else ''))
            if manual or result.errors or persistence_errors:
                lines = [f'{tr("Папка игры:")} {result.root}', '', tr(result.summary()), '', tr('Прочитанные таблицы:')]
                lines.extend(str(p.relative_to(result.root)) for p in result.files)
                if result.errors or persistence_errors:
                    lines += ['', tr('Ошибки:'), *(result.errors + persistence_errors)]
                if result.conflicts:
                    lines += ['', tr('Конфликты ID (основная таблица имеет приоритет):'), *result.conflicts]
                self._show_text('Результаты сканирования', chr(10).join(lines))

    def choose_game_folder(self):
        path = filedialog.askdirectory(title='Папка Cold Steel III (содержит каталог data)',
             initialdir=self.settings.get('game_root') or str(Path.home()), mustexist=True)
        if path:
            self.start_scan(manual=True, folder=path)

    def _make_ui(self):
        header = ttk.Frame(self, style='Header.TFrame', padding=(18,14,18,14))
        header.pack(fill='x')
        ttk.Label(header, text='COLD STEEL III  /  ИНВЕНТАРЬ', style='Title.TLabel').pack(side='left')
        ttk.Label(header,text='  •  ВЕРСИЯ 7.0',style='CardMuted.TLabel').pack(side='left')
        self.theme_combo = ttk.Combobox(header, state='readonly', width=10,
                         textvariable=self.theme_var,
                         values=('Dark','Light') if self.language=='en' else ('Тёмная','Светлая'))
        self.theme_combo.pack(side='right', padx=(8,0))
        ttk.Label(header, text='Оформление', style='CardMuted.TLabel').pack(side='right')
        self.theme_combo.bind('<<ComboboxSelected>>', lambda _e: self.apply_theme())
        self.language_combo = ttk.Combobox(header, state='readonly', width=10,
                         textvariable=self.language_var, values=('Русский','English'))
        self.language_combo.pack(side='right', padx=(8,14))
        ttk.Label(header, text='Язык', style='CardMuted.TLabel').pack(side='right')
        self.language_combo.bind('<<ComboboxSelected>>', lambda _e: self.change_language())

        filesbar = ttk.Frame(self, padding=(14,12,14,5))
        filesbar.pack(fill='x')
        ttk.Button(filesbar, text='Последнее сохранение  F5', command=self.load_latest_save,
                   style='Accent.TButton').pack(side='left', padx=(0,7))
        ttk.Button(filesbar, text='Открыть вручную  Ctrl+O', command=self.open_save).pack(side='left',padx=(0,7))
        ttk.Button(filesbar, text='Сравнить два файла', command=self.compare_saves).pack(side='left')
        ttk.Button(filesbar, text='Сохранить копию…  Ctrl+S', command=self.save_copy).pack(side='right')
        ttk.Button(filesbar, text='Записать с резервной копией',command=self.save_overwrite).pack(side='right',padx=(0,7))
        saveline=ttk.Frame(self,padding=(16,1,14,5))
        saveline.pack(fill='x')
        ttk.Label(saveline,textvariable=self.save_line,style='Info.TLabel').pack(side='left')
        ttk.Checkbutton(saveline,text='Автовыбор при запуске', variable=self.auto_latest,
                        command=self._on_auto_change).pack(side='right')
        # Advanced controls are available with one click, not occupying
        # four toolbar rows during normal item editing.
        advanced_head=ttk.Frame(self,padding=(14,1,14,7))
        advanced_head.pack(fill='x')
        self.tools_button=ttk.Button(advanced_head,text='Инструменты и игровые ресурсы  ▾',
                                     command=self.toggle_tools)
        self.tools_button.pack(side='left')
        ttk.Label(advanced_head,textvariable=self.icon_status,
                  style='Info.TLabel').pack(side='right')
        self.tools_frame=ttk.Frame(self)
        gamebar=ttk.Frame(self.tools_frame,padding=(14,6,14,6))
        gamebar.pack(fill='x')
        self.scan_button=ttk.Button(gamebar,text='Сканировать игру и DLC',
                              command=lambda:self.start_scan(manual=True))
        self.scan_button.pack(side='left',padx=(0,7))
        ttk.Button(gamebar,text='Выбрать папку игры',command=self.choose_game_folder).pack(side='left',padx=(0,7))
        ttk.Button(gamebar,text='Импорт .tbl / .csv',command=self.open_catalog).pack(side='left',padx=(0,8))
        ttk.Button(gamebar,text='Импорт английского .tbl',command=self.import_english_catalog).pack(side='left')
        ttk.Button(gamebar,text='Отчёт о переводе DLC',command=self.export_missing_translations).pack(side='left',padx=(7,0))
        ttk.Button(gamebar,text='Импорт перевода DLC',command=self.import_ru_dlc_translations).pack(side='left',padx=(7,0))
        ttk.Label(gamebar,textvariable=self.scan_info,style='Info.TLabel').pack(side='right')
        iconsbar=ttk.Frame(self.tools_frame,padding=(14,0,14,9))
        iconsbar.pack(fill='x')
        self.icons_button=ttk.Button(iconsbar,text='Загрузить оригинальные иконки',
                   command=lambda:self.start_icon_download(manual=True))
        self.icons_button.pack(side='left',padx=(0,10))
        ttk.Button(iconsbar,text='Импорт папки PNG',command=self.choose_icon_folder).pack(side='left',padx=(0,11))
        ttk.Label(iconsbar,text='Поддержка подарков и четырёх видов EX-сфер',
                  style='Info.TLabel').pack(side='right')
        self.main_separator=ttk.Separator(self)
        self.main_separator.pack(fill='x')

        bottom=ttk.Frame(self,padding=(14,4,14,11))
        bottom.pack(side='bottom',fill='x')
        ttk.Label(bottom,textvariable=self.catalog_status,style='Info.TLabel').pack(anchor='w',pady=(0,5))
        ttk.Separator(bottom).pack(fill='x',pady=(0,7))
        ttk.Label(bottom,textvariable=self.status,style='Info.TLabel').pack(anchor='w')

        # Static two-column layout: the details panel is intentionally not
        # resizable. This removes the last source of visible lag reported on
        # Windows when dragging the right-hand divider.
        center=ttk.Frame(self,style='App.TFrame')
        center.pack(fill='both',expand=True,padx=12,pady=(12,7))
        left=ttk.Frame(center,style='App.TFrame')
        left.pack(side='left',fill='both',expand=True,padx=(0,12))
        right=ttk.Frame(center,style='Card.TFrame',padding=(18,15,18,15),width=340)
        right.pack(side='right',fill='y')
        right.pack_propagate(False)

        self.tabs=ttk.Notebook(left)
        self.tabs.pack(fill='both',expand=True)
        page_inv=ttk.Frame(self.tabs,style='Card.TFrame',padding=(12,12,12,9))
        page_all=ttk.Frame(self.tabs,style='Card.TFrame',padding=(12,12,12,9))
        self.tabs.add(page_all,text=tr('Каталог и добавление'))
        self.tabs.add(page_inv,text=tr('Мой инвентарь'))

        ttk.Label(page_inv,text='Поиск предмета в сохранении',style='Card.TLabel').pack(anchor='w')
        inv_search_row=ttk.Frame(page_inv,style='Card.TFrame')
        inv_search_row.pack(fill='x',pady=(6,10))
        ttk.Entry(inv_search_row,textvariable=self.search_inv).pack(side='left',fill='x',expand=True)
        ttk.Button(inv_search_row,text='Очистить',command=lambda:self.search_inv.set('')).pack(side='left',padx=(6,0))
        self.tree=self._new_tree(page_inv,[('slot','Слот',65),('id','ID',65),('qty','Кол-во',75)], icons=True, name_width=300, sort_kind='inventory')
        self.tree.bind('<<TreeviewSelect>>',lambda _e:self._select_from_tree(self.tree))

        ttk.Label(page_all,text='Выберите группу, затем предмет',style='Section.TLabel').pack(anchor='w',pady=(0,9))
        catalog_panel=ttk.Frame(page_all,style='Card.TFrame')
        catalog_panel.pack(fill='both',expand=True)
        side=ttk.Frame(catalog_panel,style='Card.TFrame',width=238)
        side.pack(side='left',fill='y',padx=(0,10))
        side.pack_propagate(False)
        ttk.Label(side,text='ГРУППЫ',style='CardMuted.TLabel').pack(anchor='w',pady=(0,7))
        self.category_tree=ttk.Treeview(side,show='tree',style='Category.Treeview',
                                selectmode='browse',height=16)
        self.category_tree.pack(side='left',fill='both',expand=True)
        category_scroll=ttk.Scrollbar(side,orient='vertical',command=self.category_tree.yview)
        category_scroll.pack(side='right',fill='y')
        self.category_tree.configure(yscrollcommand=category_scroll.set)
        self.category_tree.column('#0',width=225,stretch=False)
        self.category_tree.bind('<<TreeviewSelect>>',self._on_category_change)
        self._populate_categories()
        table_side=ttk.Frame(catalog_panel,style='Card.TFrame')
        table_side.pack(side='left',fill='both',expand=True)
        ttk.Label(table_side,text='Поиск по названию, ID или описанию',style='Card.TLabel').pack(anchor='w')
        catalog_search_row=ttk.Frame(table_side,style='Card.TFrame')
        self.catalog_search_entry=ttk.Entry(catalog_search_row,textvariable=self.search_all)
        catalog_search_row.pack(fill='x',pady=(6,7))
        self.catalog_search_entry.pack(side='left',fill='x',expand=True)
        ttk.Button(catalog_search_row,text='Очистить',command=lambda:self.search_all.set('')).pack(side='left',padx=(6,0))
        ttk.Checkbutton(table_side,text='Показывать только отсутствующие',
                        variable=self.only_missing,style='Card.TCheckbutton').pack(anchor='w',pady=(0,8))
        # Reserve this action row *before* the expanding Treeview so the
        # batch button remains visible even at the window's minimum height.
        bulk_bar=ttk.Frame(table_side,style='Card.TFrame')
        bulk_bar.pack(fill='x',pady=(0,7))
        ttk.Label(bulk_bar,text='Ctrl / Shift — выбрать несколько предметов',
                  style='CardMuted.TLabel').pack(side='left',anchor='center')
        self.bulk_button=ttk.Button(bulk_bar,text='Добавить выбранные предметы',
                                     command=self.apply_bulk_change,style='Accent.TButton')
        self.bulk_button.pack(side='right')
        self.all_tree=self._new_tree(table_side,[('id','ID',65),('type','Категория',165),('qty','В сумке',75)], icons=True, name_width=265, sort_kind='catalog', multi=True)
        self.all_tree.bind('<<TreeviewSelect>>',lambda _e:self._select_from_tree(self.all_tree))
        self._update_sort_headers('inventory')
        self._update_sort_headers('catalog')

        ttk.Label(right,text='ВЫБРАННЫЙ ПРЕДМЕТ',style='Section.TLabel').pack(anchor='w',pady=(0,11))
        values=ttk.Frame(right,style='Card.TFrame')
        values.pack(fill='x',pady=(0,12))
        left_value=ttk.Frame(values,style='Card.TFrame')
        left_value.pack(side='left',fill='x',expand=True,padx=(0,10))
        right_value=ttk.Frame(values,style='Card.TFrame')
        right_value.pack(side='left',fill='x',expand=True)
        ttk.Label(left_value,text='ID предмета',style='CardMuted.TLabel').pack(anchor='w')
        ttk.Entry(left_value,textvariable=self.item_var).pack(fill='x',pady=(5,0))
        ttk.Label(right_value,text='Количество',style='CardMuted.TLabel').pack(anchor='w')
        ttk.Spinbox(right_value,from_=0,to=MAX_QUANTITY,textvariable=self.qty_var).pack(fill='x',pady=(5,0))
        ttk.Button(right,text='Добавить / применить количество',command=self.apply_change,
                   style='Accent.TButton').pack(fill='x',pady=(0,8))
        ttk.Button(right,text='Удалить предмет из сохранения',command=self.delete_selected,
                   style='Danger.TButton').pack(fill='x',pady=(0,12))
        actions=ttk.Frame(right,style='Card.TFrame')
        actions.pack(fill='x')
        ttk.Button(actions,text='↶ Отменить',command=self.undo).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(actions,text='Сбросить правки',command=self.revert).pack(side='left',fill='x',expand=True)
        ttk.Separator(right).pack(fill='x',pady=(18,12))
        # Reserve space for this safety warning BEFORE the expanding Text widget.
        # Otherwise the warning can be truncated on smaller screens/window sizes.
        ttk.Label(right,text='Изменения вносятся только в файл сохранения. '
                 'Закройте игру перед записью.',style='CardMuted.TLabel',
                  wraplength=295).pack(side='bottom',fill='x',pady=(10,0))
        ttk.Label(right,text='Описание и характеристики',style='Section.TLabel').pack(anchor='w',pady=(0,7))
        descframe=ttk.Frame(right,style='Card.TFrame')
        descframe.pack(fill='both',expand=True)
        self.details=tk.Text(descframe,height=10,width=29,wrap='word',state='disabled',
                             borderwidth=1,relief='solid',padx=12,pady=10,
                             font=('Segoe UI',10),spacing2=3)
        self.details.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(descframe,command=self.details.yview)
        scrollbar.pack(side='right',fill='y')
        self.details.configure(yscrollcommand=scrollbar.set)
        self._describe(None)
        self.apply_theme(save=False)

    def change_language(self):
        self.language='en' if self.language_var.get()=='English' else 'ru'
        set_language(self.language)
        self.settings['language']=self.language
        try: save_settings(self.settings)
        except OSError: pass
        self.theme_var.set(('Dark' if self.language=='en' else 'Тёмная')
                           if self.settings.get('theme','dark')=='dark' else
                           ('Light' if self.language=='en' else 'Светлая'))
        self.theme_combo['values']=('Dark','Light') if self.language=='en' else ('Тёмная','Светлая')
        self._translate_widgets(self)
        self.tabs.tab(0,text=tr('Каталог и добавление'))
        self.tabs.tab(1,text=tr('Мой инвентарь'))
        for var in (self.icon_status,self.scan_info,self.save_line,self.status,self.catalog_status):
            var.relocalize()
        self._update_sort_headers('inventory')
        self._update_sort_headers('catalog')
        self._populate_categories()
        self._refresh()
        self._describe(self.selected_item)
        self.apply_theme(save=False)
        if self.language=='en' and not self.english_catalog:
            self.status.set('Английский каталог не загружен. Импортируйте оригинальную таблицу через «Инструменты».')

    @staticmethod
    def _translate_widgets(parent):
        for widget in parent.winfo_children():
            source=getattr(widget,'_ru_ui_text',None)
            if source is not None:
                try: widget.configure(text=tr(source))
                except tk.TclError: pass
            Editor._translate_widgets(widget)

    def import_english_catalog(self):
        file = filedialog.askopenfilename(
            title='Оригинальная английская таблица предметов (из игры без русификации)',
            filetypes=[('Таблица предметов', '*.tbl'),('Все файлы','*.*')])
        if not file: return
        try:
            data=load_external_catalog(file)
            # Never accidentally load the user's Russian localization as English.
            cyrillic=sum(bool(__import__('re').search('[А-Яа-яЁё]',v['name']))
                         for v in data.values())
            descs = [v.get('description','') for v in data.values() if v.get('description')]
            cyrillic_desc = sum(bool(__import__('re').search('[А-Яа-яЁё]',d)) for d in descs)
            if cyrillic / len(data) > 0.05 or (descs and cyrillic_desc/len(descs) > 0.10):
                raise ValueError('Похоже, этот файл содержит русский перевод, а не оригинальную английскую таблицу.')
            self.english_catalog.update(data)
            save_catalog_json(config_dir()/'catalog_english.json',self.english_catalog)
            self._refresh()
            messagebox.showinfo('Английский каталог импортирован',
                 f'Загружено названий и описаний: {len(data)}. '
                 f'Всего английских записей: {len(self.english_catalog)}.')
        except (ValueError,OSError,KeyError) as exc:
            messagebox.showerror('Ошибка импорта английского каталога',str(exc))

    def import_ru_dlc_translations(self):
        path=filedialog.askopenfilename(title='Импорт перевода DLC (CSV из отчёта)',
             filetypes=[('CSV UTF-8','*.csv'),('Все файлы','*.*')])
        if not path:
            return
        try:
            updates={}
            with open(path,encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f)
                if not reader.fieldnames or not {'ID','Russian name','Russian description'} <= set(reader.fieldnames):
                    raise ValueError('Нужны столбцы ID, Russian name, Russian description.')
                for row in reader:
                    raw=(row.get('ID') or '').strip()
                    if not raw:
                        continue
                    item_id=int(raw)
                    if item_id not in self.catalog:
                        continue
                    name=(row.get('Russian name') or '').strip()
                    desc=(row.get('Russian description') or '').strip()
                    if not name and not desc:
                        continue
                    if name and not __import__('re').search('[А-Яа-яЁё]',name):
                        raise ValueError(f'ID {item_id}: русский перевод названия отсутствует.')
                    if desc and not __import__('re').search('[А-Яа-яЁё]',desc):
                        raise ValueError(f'ID {item_id}: русский перевод описания отсутствует.')
                    existing=self.user_overrides.get(item_id,self.catalog[item_id]).copy()
                    existing.update({'id':item_id})
                    if name:
                        existing['name']=name
                    if desc:
                        existing['description']=desc
                    updates[item_id]=existing
            if not updates:
                raise ValueError('В CSV нет заполненных переводов для известных предметов.')
            new_overrides={**self.user_overrides,**updates}
            save_catalog_json(user_catalog_path(),new_overrides)
            self.user_overrides=new_overrides
            self._rebuild_catalog()
            self._refresh()
            messagebox.showinfo('Импорт перевода DLC',f'Загружено переводов: {len(updates)}.')
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showerror('Ошибка импорта перевода',str(exc))

    def export_missing_translations(self):
        missing=missing_ru_entries(self.catalog,self.builtin)
        if not missing:
            messagebox.showinfo('Переводы DLC', 'Непереведённых английских записей DLC не обнаружено.')
            return
        path=filedialog.asksaveasfilename(title='Сохранить список непереведённых DLC',
             defaultextension='.csv',initialfile='CS3_untranslated_DLC.csv',
             filetypes=[('CSV UTF-8','*.csv')])
        if not path:
            return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f)
                writer.writerow(['ID','English name','English description','Russian name','Russian description'])
                writer.writerows([row['id'],row['name'],row['description'],'',''] for row in missing)
            messagebox.showinfo('Переводы DLC',
                f'Записей без проверенного русского перевода: {len(missing)}.\nОтчёт сохранён: {path}')
        except OSError as exc:
            messagebox.showerror('Не удалось создать отчёт',str(exc))

    def toggle_tools(self):
        self.tools_expanded=not self.tools_expanded
        if self.tools_expanded:
            # Anchor before the central pane so the catalog remains visible.
            self.tools_frame.pack(fill='x',before=self.main_separator)
        else:
            self.tools_frame.pack_forget()
        text='Скрыть инструменты  ▴' if self.tools_expanded else 'Инструменты и игровые ресурсы  ▾'
        self.tools_button._ru_ui_text=text
        self.tools_button.configure(text=tr(text))

    def _populate_categories(self):
        counts={key:0 for key in CATEGORY_NAMES}
        for item in self.catalog.values():
            if is_visible_item(item):
                counts[category_of(item)] += 1
        self.category_tree.delete(*self.category_tree.get_children())
        self.category_tree.insert('','end',iid='all',text=f'{tr("Все предметы")}  ({sum(is_visible_item(v) for v in self.catalog.values())})')
        for group,(name,subgroups) in GROUPS.items():
            count=sum(counts[k] for k,_ in subgroups)
            self.category_tree.insert('','end',iid=group,text=f'{tr(name)}  ({count})',open=True)
            for cat,label in subgroups:
                self.category_tree.insert(group,'end',iid=cat,text=f'{tr(label)}  ({counts[cat]})')
        selected=self.active_category if self.category_tree.exists(self.active_category) else 'all'
        self.category_tree.selection_set(selected)
        self.category_tree.see(selected)

    def _on_category_change(self, _event=None):
        if not self.category_tree.selection():
            return
        self.active_category=self.category_tree.selection()[0]
        if hasattr(self,'all_tree'):
            self.refresh_catalog()

    def _on_auto_change(self):
        self.settings['auto_latest']=self.auto_latest.get()
        try: save_settings(self.settings)
        except OSError as exc: messagebox.showerror('Настройки',str(exc))

    def destroy(self):
        """Cancel pending Tk timers before widgets and Tcl callbacks disappear."""
        pending=list(getattr(self,'_startup_jobs',[]))
        pending.extend(getattr(self,'_search_jobs',{}).values())
        pending.extend((getattr(self,'_scan_poll_job',None),
                        getattr(self,'_icon_poll_job',None)))
        for job in pending:
            if job is not None:
                try:self.after_cancel(job)
                except (tk.TclError,ValueError):pass
        if hasattr(self,'_startup_jobs'):self._startup_jobs.clear()
        if hasattr(self,'_search_jobs'):self._search_jobs.clear()
        self._scan_poll_job=self._icon_poll_job=None
        super().destroy()

    def on_close(self):
        if self.save and self.save.changed and not messagebox.askyesno(
                'Несохранённые изменения',
                'Есть правки, которые не были записаны в файл. Закрыть программу без сохранения?'):
            return
        self.destroy()

    def focus_catalog_search(self, _event=None):
        self.tabs.select(0)
        # find the Entry bound to search_all from the catalog panel
        if hasattr(self,'catalog_search_entry'):
            self.catalog_search_entry.focus_set()

    def load_latest_save(self, manual=True):
        """Pick newest compatible save; never discard unsaved changes silently."""
        if self.save and self.save.changed and not messagebox.askyesno(
                'Несохранённые изменения', 'Открыть последнее сохранение и потерять текущие правки?'):
            return
        folders=save_directories(self.settings.get('save_directory'))
        match,warnings=newest_compatible_save(folders)
        if match is None:
            hint='Совместимые saveXXX.dat не найдены. Откройте сохранение вручную.'
            self.save_line.set(hint)
            if manual:
                messagebox.showwarning('Последнее сохранение', hint+'\n\n' + '\n'.join(warnings[:4]))
            return
        self._accept_save(match.path, match.save, auto=True)
        if manual and warnings:
            messagebox.showinfo('Последнее сохранение',
                f'Загружено {match.path.name}. Пропущено некорректных файлов: {len(warnings)}.')

    def _accept_save(self, path: Path, save: CS3Save, auto=False):
        from datetime import datetime
        self.source,self.save=path.resolve(),save
        self._history.clear()
        self.selected_item=None
        self.item_var.set('')
        self.qty_var.set('1')
        self.settings['save_directory']=str(self.source.parent)
        try: save_settings(self.settings)
        except OSError: pass
        when=datetime.fromtimestamp(self.source.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
        self.save_line.set(f'{"Автоматически выбрано" if auto else "Открыто вручную"}: '
                           f'{self.source.name}  •  {when}  •  {self.source.parent}')
        self._refresh()
        self._describe(None)

    def _new_tree(self, parent, cols, icons=False, name_width=270, sort_kind=None, multi=False):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        keys = [c[0] for c in cols]
        tree = ttk.Treeview(frame, columns=keys, show='tree headings' if icons else 'headings', selectmode='extended' if multi else 'browse')
        if icons:
            tree.heading('#0', text=tr('Предмет'), command=(lambda k=sort_kind:self.sort_table(k, 'name')) if sort_kind else None)
            tree.column('#0', width=name_width, minwidth=145, stretch=True, anchor='w')
        for key, title, width in cols:
            tree.heading(key, text=tr(title),
                         command=(lambda k=sort_kind,c=key:self.sort_table(k,c)) if sort_kind else None)
            tree.column(key, width=width, anchor='w' if key == 'name' else 'center', stretch=(key == 'name'))
        tree.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, command=tree.yview)
        scroll.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scroll.set)
        return tree

    def _schedule_filter(self, table):
        """Coalesce keystrokes: no 1200-row rebuild on every typed character."""
        previous=self._search_jobs.pop(table,None)
        if previous is not None:
            self.after_cancel(previous)
        def callback():
            self._search_jobs.pop(table,None)
            if table == 'inventory':self.refresh_inventory()
            else:self.refresh_catalog()
        self._search_jobs[table]=self.after(135,callback)

    def sort_table(self, table, column):
        """Sort both ways by clicking a header, preserving active search/group."""
        if table not in self._sort_state:
            return
        previous,reverse=self._sort_state[table]
        self._sort_state[table]=(column, not reverse if previous == column else False)
        self._update_sort_headers(table)
        if table == 'inventory':self.refresh_inventory()
        else:self.refresh_catalog()

    def _update_sort_headers(self, table):
        tree=self.tree if table=='inventory' else self.all_tree
        labels=(('#0','Предмет'),('slot','Слот'),('id','ID'),('qty','Кол-во')) if table=='inventory' else (
                ('#0','Предмет'),('id','ID'),('type','Категория'),('qty','В сумке'))
        column,reverse=self._sort_state[table]
        for cid,label in labels:
            tree.heading(cid,text=tr(label)+(' ▼' if reverse else ' ▲') if (cid=='#0' and column=='name') or column==cid else tr(label))

    def _sorted_entries(self, table, rows):
        """Stable numeric sort for quantity/ID/slot, natural text sort elsewhere."""
        column,reverse=self._sort_state[table]
        if table=='inventory':
            # Each row is (item_id, name, slot, quantity).
            keys={'name':lambda r:(r[1].casefold(),r[0]),
                  'id':lambda r:r[0], 'slot':lambda r:r[2],
                  'qty':lambda r:(r[3],r[1].casefold(),r[0])}
        else:
            # Each row is (item_id, name, category, quantity).
            keys={'name':lambda r:(r[1].casefold(),r[0]),
                  'id':lambda r:r[0], 'type':lambda r:(r[2].casefold(),r[1].casefold(),r[0]),
                  'qty':lambda r:(r[3],r[1].casefold(),r[0])}
        return sorted(rows,key=keys.get(column,keys['name']),reverse=reverse)

    @staticmethod
    def _replace_tree_rows(tree, rows, item_factory):
        """Repopulate rows once, restoring selection and scroll where feasible."""
        old_selection=tree.selection()
        old_focus=tree.focus()
        # Keeping vertical fraction stops the view jumping to the top on sort.
        position=tree.yview()[0]
        children=tree.get_children()
        if children:tree.delete(*children)
        for index,row in enumerate(rows):
            iid,text,icon,values=item_factory(row)
            tree.insert('', 'end', iid=iid, text=text, image=icon,
                        values=values, tags=('stripe',) if index%2 else ())
        kept=[iid for iid in old_selection if tree.exists(iid)]
        if kept:
            tree.selection_set(kept)
        if old_focus and tree.exists(old_focus):
            tree.focus(old_focus)
        if rows and position:
            tree.yview_moveto(position)

    def _item_image(self, item_id):
        """Use verified artwork with one image per path and one disk lookup per ID.

        Rebuild caches only when catalog/icons change. Repeated sorting,
        filtering, and dragging never have to verify 1000+ files again.
        """
        if item_id in self._resolved_icon_paths:
            asset=self._resolved_icon_paths[item_id]
        else:
            record=self.catalog.get(item_id,{})
            category=category_of(record)
            manual=resource_path('icons')
            original=icon_file_for_item(item_id,record,manual_dir=manual)
            fallback=manual/'by_category'/(category+'.png')
            asset=original if original is not None else fallback
            self._resolved_icon_paths[item_id]=asset
        if not asset.is_file():
            return ''
        key=str(asset)
        if key in self._item_images:
            return self._item_images[key]
        try:
            icon=tk.PhotoImage(file=key,master=self)
            # Game UI textures may be larger than inventory rows; retain aspect.
            if max(icon.width(),icon.height()) > 26:
                factor=(max(icon.width(),icon.height())+25)//26
                icon=icon.subsample(factor,factor)
        except (tk.TclError,OSError):
            return ''
        self._item_images[key]=icon
        return icon

    def _get_name(self, item_id):
        if self.language == 'en':
            original = self.english_catalog.get(item_id)
            if original and original.get('name'):
                return original['name']
        fallback = self.catalog.get(item_id, {}).get('name')
        if fallback:
            if self.language == 'ru' and item_id not in self.builtin and is_english_only(fallback):
                return '[EN] ' + fallback
            if self.language == 'en':
                # English-only GitHub builds can display the actual name as is.
                import re
                return '[RU] ' + fallback if re.search(r'[А-Яа-яЁё]',fallback) else fallback
            if (not self.builtin and item_id in self.english_catalog
                    and self.english_catalog[item_id].get('name') == fallback):
                # Russian translation was never imported; mark English text.
                return '[EN] ' + fallback
            return fallback
        return f'ID {item_id} {tr("(нет названия)")}'

    def _get_description(self, item_id):
        if self.language == 'en':
            original = self.english_catalog.get(item_id)
            if original is not None:
                return original.get('description','')
            # A visibly marked fallback is safer than a fabricated translation.
            return '[Original English text not imported for this ID.]'
        if (not self.builtin and item_id in self.english_catalog
                and self.catalog.get(item_id,{}).get('name') == self.english_catalog[item_id].get('name')):
            return '[Original Russian text not imported for this ID.]'
        desc = self.catalog.get(item_id, {}).get('description','')
        if is_english_only(desc):
            return '[EN — нет русского перевода] ' + desc
        return desc

    def _category_name(self, item):
        return tr(CATEGORY_NAMES[category_of(item)])

    def _describe(self, item_id):
        item = self.catalog.get(item_id, {}) if item_id is not None else {}
        if item_id is None:
            content = tr('Выберите предмет в одной из вкладок, чтобы увидеть его описание.')
        else:
            name = self._get_name(item_id)
            text = clear_codes(self._get_description(item_id))
            content = f'{name}\nID: {item_id}\n'
            content += f'{tr("Категория:")} {self._category_name(item)}\n'
            if self.save:
                content += f'{tr("В инвентаре:")} {self.save.get_quantity(item_id)}\n'
            content += '\n' + (text or tr('Нет описания в загруженной таблице.'))
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', content)
        self.details.configure(state='disabled')

    def _select_from_tree(self, tree):
        selection = tree.selection()
        if not selection:
            return
        # Identifiers remain stable even when names are rendered in Treeview #0.
        focus = tree.focus()
        item_id = int((focus if focus in selection else selection[-1])[3:])
        self._select_item(item_id)
        if tree is self.all_tree and len(selection)>1:
            self.status.set(f'Выбрано предметов: {len(selection)}. Укажите общее количество и нажмите «Добавить выбранные предметы».')

    def _select_item(self, item_id):
        self.selected_item = item_id
        self.item_var.set(str(item_id))
        qty = self.save.get_quantity(item_id) if self.save else 0
        self.qty_var.set(str(qty if qty else 1))
        self._describe(item_id)

    def _status(self):
        if self.save and self.source:
            changed = 'Изменения не записаны' if self.save.changed else 'Без изменений'
            self.status.set(f'{self.source.name}  |  {self.save.occupied_count} предметов в инвентаре  |  '
                            f'Каталог: {sum(is_visible_item(v) for v in self.catalog.values())} названий  |  {changed}')

    def refresh_inventory(self):
        if self.save is None:
            self._replace_tree_rows(self.tree,[],lambda row:row)
            return
        needle = self.search_inv.get().strip().casefold()
        rows=[]
        for item in self.save.items():
            name=self._get_name(item.item_id)
            record=self.catalog.get(item.item_id,{'name':name})
            if not is_visible_item(record):continue
            french=record.get('fr','')
            if needle and not any(needle in z.casefold() for z in (str(item.item_id),name,french,record.get('name',''))):
                continue
            rows.append((item.item_id,name,item.slot+1,item.quantity))
        rows=self._sorted_entries('inventory',rows)
        self._replace_tree_rows(self.tree,rows,lambda r:(
            f'inv{r[0]}',r[1],self._item_image(r[0]),(r[2],r[0],r[3])))
        self._status()

    def refresh_catalog(self):
        needle = self.search_all.get().strip().casefold()
        filter_missing = self.only_missing.get()
        occupied = {i.item_id: i.quantity for i in self.save.items()} if self.save else {}
        rows=[]
        for item_id,item in self.catalog.items():
            if not is_visible_item(item):continue
            if not item_in_category(item,self.active_category):continue
            quantity=occupied.get(item_id,0)
            if filter_missing and quantity>0:continue
            if needle and not any(needle in str(v).casefold() for v in (
                    item_id,self._get_name(item_id),item['name'],item.get('fr',''),self._get_description(item_id),item.get('description',''))):continue
            rows.append((item_id,self._get_name(item_id),self._category_name(item),quantity))
        rows=self._sorted_entries('catalog',rows)
        self._replace_tree_rows(self.all_tree,rows,lambda r:(
            f'all{r[0]}',r[1],self._item_image(r[0]),(r[0],r[2],r[3])))
        untranslated=len(missing_ru_entries(self.catalog,self.builtin))
        self.catalog_status.set(f'Каталог: {sum(is_visible_item(v) for v in self.catalog.values())} предметов  |  в выбранной группе: {len(rows)}  |  '
                                f'непереведённых DLC: {untranslated}')

    def _refresh(self):
        self.refresh_inventory()
        self.refresh_catalog()
        if self.selected_item is not None:
            self._describe(self.selected_item)

    def _require_save(self):
        if self.save is not None:
            return True
        messagebox.showinfo('Откройте сохранение', 'Сначала откройте saveXXX.dat. Каталог доступен без сохранения.')
        return False

    def open_save(self):
        if self.save and self.save.changed and not messagebox.askyesno(
                'Несохранённые изменения', 'Открыть другое сохранение и потерять изменения?'):
            return
        folders=save_directories(self.settings.get('save_directory'))
        default_dir = Path(self.settings.get('save_directory') or (folders[0] if folders else Path.home()))
        name = filedialog.askopenfilename(title='Открыть saveXXX.dat',
                 initialdir=str(default_dir if default_dir.is_dir() else Path.home()),
                 filetypes=[('Сохранения игры','*.dat'), ('Все файлы','*.*')])
        if not name:
            return
        try:
            src = Path(name).resolve()
            save = CS3Save.from_file(src)
            self._accept_save(src, save)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Не удалось открыть сохранение', str(exc))

    def apply_change(self, target_qty=None):
        if (target_qty is None and self.tabs.select() == str(self.tabs.tabs()[0])
                and hasattr(self,'all_tree') and len(self.all_tree.selection()) > 1):
            return self.apply_bulk_change()
        if not self._require_save():
            return
        try:
            raw_id = self.item_var.get().strip()
            item_id = int(raw_id, 16) if raw_id.lower().startswith('0x') else int(raw_id)
            qty = int(self.qty_var.get().strip()) if target_qty is None else target_qty
            assert self.save is not None
            previous = self.save.get_quantity(item_id)
            if qty > 0 and not previous and item_id not in self.catalog:
                if not messagebox.askyesno('Неизвестный предмет',
                        f'ID {item_id} отсутствует в каталоге. Он может быть недопустимым. Продолжить?'):
                    return
            if previous == qty:
                self.status.set(f'ID {item_id}: уже установлено количество {qty}')
                return
            snapshot = self.save.bytes()
            try:
                self.save.set_quantity(item_id, qty)
            except Exception:
                self.save._data = bytearray(snapshot)
                raise
            self._history.append(snapshot)
            if len(self._history)>40:
                self._history.pop(0)
            self._refresh()
            self._select_item(item_id)
            iid = f'inv{item_id}'
            if qty > 0 and self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)
        except (ValueError, SaveFormatError) as exc:
            messagebox.showerror('Не удалось изменить предмет', str(exc))

    def apply_bulk_change(self):
        """Atomically assign the same stack quantity to all catalog selections."""
        if not self._require_save():
            return
        ids=sorted({int(iid[3:]) for iid in self.all_tree.selection()
                    if iid.startswith('all')})
        if not ids:
            messagebox.showinfo('Выбор предметов', 'Выделите предметы в каталоге. Используйте Ctrl или Shift для нескольких строк.')
            return
        try:
            qty=int(self.qty_var.get().strip())
            if not 1 <= qty <= MAX_QUANTITY:
                raise ValueError(f'Количество должно быть в диапазоне 1–{MAX_QUANTITY}')
            assert self.save is not None
            existing={v.item_id: v.quantity for v in self.save.items()}
            changes=[item_id for item_id in ids if existing.get(item_id,0)!=qty]
            if not changes:
                self.status.set('У выбранных предметов уже установлено указанное количество.')
                return
            missing=sum(1 for item_id in changes if item_id not in existing)
            if self.save.occupied_count + missing > 6144 - 16:
                raise ValueError('Недостаточно свободных слотов для выбранных предметов')
            if not messagebox.askyesno('Массовое добавление',
                    f'Установить количество {qty} для {len(changes)} предметов?\n'
                    f'Новых предметов: {missing}. Уже имеющиеся будут изменены до {qty}.'):
                return
            snapshot=self.save.bytes()
            self.save.set_quantities({item_id: qty for item_id in changes})
            self._history.append(snapshot)
            if len(self._history)>40:
                self._history.pop(0)
            self._refresh()
            kept=[f'all{item_id}' for item_id in ids if self.all_tree.exists(f'all{item_id}')]
            if kept:
                self.all_tree.selection_set(kept)
            self.status.set(f'Обновлено предметов: {len(changes)}. Новых: {missing}. Изменения ещё не сохранены.')
        except (ValueError,SaveFormatError) as exc:
            messagebox.showerror('Не удалось добавить выбранные предметы',str(exc))

    def delete_selected(self):
        if not self._require_save():
            return
        if not self.item_var.get().strip():
            messagebox.showinfo('Нужен ID', 'Выберите предмет в списке или введите ID')
            return
        if messagebox.askyesno('Удаление', f'Удалить ID {self.item_var.get()} из сохранения?'):
            self.apply_change(target_qty=0)

    def undo(self):
        if not self._require_save():
            return
        if not self._history:
            messagebox.showinfo('Отмена', 'Нет действий для отмены')
            return
        assert self.save is not None
        self.save._data = bytearray(self._history.pop())
        self._refresh()

    def revert(self):
        if not self._require_save():
            return
        if messagebox.askyesno('Сброс изменений', 'Отменить все изменения текущего сохранения?'):
            assert self.save is not None
            self.save.reset()
            self._history.clear()
            self._refresh()

    def open_catalog(self):
        name = filedialog.askopenfilename(title='Импорт новой таблицы или DLC',
            filetypes=[('Таблицы предметов', '*.tbl *.csv'),('Все файлы','*.*')])
        if not name:
            return
        try:
            imported = load_external_catalog(name)
            new_count = len(set(imported) - set(self.catalog))
            # Manually imported names override automatic game data, across restarts.
            for item_id, entry in imported.items():
                previous = self.user_overrides.get(item_id, {})
                self.user_overrides[item_id] = {**previous, **{k:v for k,v in entry.items() if v or k == 'id'}}
            save_catalog_json(user_catalog_path(), self.user_overrides)
            self._rebuild_catalog()
            self._populate_categories()
            self._refresh()
            messagebox.showinfo('Импорт завершён',
                    f'Прочитано записей: {len(imported)}\nНовых ID: {new_count}\n'
                    f'Всего названий: {len(self.catalog)}\n\nИмпорт сохранён для следующих запусков.')
        except (ValueError, OSError, KeyError) as exc:
            messagebox.showerror('Ошибка импорта', str(exc))

    def compare_saves(self):
        names = filedialog.askopenfilenames(title='Выберите ровно два файла',
                     filetypes=[('Сохранения','*.dat')])
        if not names:
            return
        if len(names) != 2:
            messagebox.showinfo('Сравнение', 'Нужно выбрать ровно 2 файла (Ctrl + клик)')
            return
        try:
            d = get_diff_summary(Path(names[0]).read_bytes(), Path(names[1]).read_bytes())
            lines = [f'{Path(names[0]).name} → {Path(names[1]).name}', '',
                f'Добавлено {len(d["added"])} / удалено {len(d["removed"])} / изменено {len(d["modified"])}',
                f'Изменений за пределами инвентаря (байт): {d["other_changed_bytes"]}', '']
            for item_id, qty in d['added']:
                lines.append(f'+ {self._get_name(item_id)} × {qty}')
            for item_id, qty in d['removed']:
                lines.append(f'− {self._get_name(item_id)} × {qty}')
            for item_id, a, b in d['modified']:
                lines.append(f'~ {self._get_name(item_id)}: {a} → {b}')
            self._show_text('Сравнение сохранений', '\n'.join(lines))
        except (ValueError, OSError) as exc:
            messagebox.showerror('Ошибка сравнения', str(exc))

    def _show_text(self, title, content):
        win = tk.Toplevel(self)
        win.title(tr(title))
        win.geometry('740x470')
        contentbox = tk.Text(win, wrap='word', background=self._colors['panel'],
                             foreground=self._colors['fg'], insertbackground=self._colors['fg'])
        contentbox.pack(fill='both', expand=True, padx=12, pady=12)
        contentbox.insert('1.0', content)
        contentbox.configure(state='disabled')

    def _write_atomic(self, target: Path, overwrite: bool):
        assert self.save is not None and self.source is not None
        payload = self.save.bytes()
        target = target.resolve()
        original_path = self.source
        if target == original_path and not overwrite:
            raise ValueError('Для записи оригинала используйте «Записать + backup»')
        if target.exists() and target != original_path:
            if not messagebox.askyesno('Файл существует', f'Перезаписать {target.name}?'):
                return False
        if target == original_path:
            current_data = original_path.read_bytes()
            if hashlib.sha256(current_data).hexdigest() != self.save.original_sha256:
                raise SaveFormatError('Файл был изменён вне редактора. Откройте его повторно.')
            backup = original_path.with_name(original_path.name + '.bak')
            if backup.exists():
                from datetime import datetime
                backup = original_path.with_name(original_path.name + '.bak-' +
                                                datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(original_path, backup)
        elif target.exists():
            from datetime import datetime
            backup = target.with_name(target.name + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(target, backup)
        fd, tmpname = tempfile.mkstemp(prefix='.cs3-editor-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(tmpname, target)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
        if target.read_bytes() != payload:
            raise OSError('Проверка записанного сохранения не пройдена')
        return True

    def save_copy(self):
        if not self._require_save():
            return
        assert self.source is not None
        name = filedialog.asksaveasfilename(title='Сохранить отдельную копию',
            initialdir=str(self.source.parent), initialfile=self.source.stem + '_edited.dat',
            defaultextension='.dat',filetypes=[('Файл сохранения','*.dat')])
        if not name:
            return
        try:
            if self._write_atomic(Path(name), False):
                messagebox.showinfo('Копия записана', f'Сохранено:\n{name}\n\nОригинал не изменён. '
                  'Для загрузки в игре скопируйте файл под именем свободного слота saveXXX.dat.')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Не удалось сохранить', str(exc))

    def save_overwrite(self):
        if not self._require_save():
            return
        assert self.save is not None and self.source is not None
        if not self.save.changed:
            messagebox.showinfo('Нет изменений', 'Нет изменений для записи')
            return
        if not messagebox.askyesno('Записать оригинал?',
            f'Перезаписать {self.source.name}?\nЗакройте игру перед записью.\n'
            'Создаётся резервная копия .bak.\n'
            'Загрузка отредактированного файла игрой пока не проверена.'):
            return
        try:
            if self._write_atomic(self.source, True):
                self._accept_save(self.source, CS3Save.from_file(self.source))
                messagebox.showinfo('Записано', 'Сохранение обновлено. Резервная копия создана.')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Ошибка записи', str(exc))


if __name__ == '__main__':
    Editor().mainloop()
