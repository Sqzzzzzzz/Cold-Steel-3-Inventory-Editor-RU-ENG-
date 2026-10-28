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
from catalog_visibility import is_visible_item, NON_INVENTORY_ITEM_IDS
from quartz_details import generated_help
from game_icons import (icon_cache_dir, icon_file_for_item,
                        download_original_icons, import_original_icons, validate_file, ALL_ORIGINAL_FILES, MASTER_QUARTZ_FILES, special_local_icon_key, OFFICIAL_SPECIAL_ICONS)
from save_scan import save_directories, newest_compatible_save
from game_scan import (find_game_install, load_settings, save_settings,
                       scan_game_tables, config_dir)
from dlc_translation import KNOWN_RUSSIAN_DLC, is_english_only, missing_ru_entries
import csv
from beta_config import seed_beta_profile
from hud_art import strip, attach_corners, HUDTab

APP_NAME = 'Cold Steel III — Inventory Editor v7.5.0 GAME HUD BETA'


class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry('1620x910')
        self.minsize(1350, 770)
        # Beta must not touch the released editor's settings/catalog/icon cache.
        # Copy user-owned translations and icons just once for easy testing.
        try:seed_beta_profile()
        except OSError:pass
        self.save: CS3Save | None = None
        self.source: Path | None = None
        self.settings = load_settings()
        self.settings['theme'] = 'game'
        self.favorites = {int(x) for x in self.settings.get('favorites', []) if str(x).isdigit()}
        self.recents = [int(x) for x in self.settings.get('recents', []) if str(x).isdigit()][:20]
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
        self._detail_images = {}
        self._resolved_icon_paths = {}
        self._sort_state = {'catalog': ('name', False), 'inventory': ('slot', False)}
        self._search_jobs = {}
        self._startup_jobs = []
        self._scan_poll_job = None
        self._icon_poll_job = None
        self._icon_events = queue.Queue()
        self._icon_downloading = False
        self.icon_status = LocalizedStringVar(value=self._icon_status_text())
        self._scan_events = queue.Queue()
        self._scanning = False
        self.scan_info = LocalizedStringVar(value='Сканирование игры: ещё не выполнялось')
        self.style = ttk.Style(self)
        self.apply_theme(save=False)
        self.search_inv = tk.StringVar()
        self.search_all = tk.StringVar()
        self.only_missing = tk.BooleanVar(value=False)
        self.only_present = tk.BooleanVar(value=False)
        self.catalog_source = tk.StringVar(value='Все источники')
        self.auto_latest = tk.BooleanVar(value=self.settings.get('auto_latest', True))
        self.active_category = 'all'
        self.save_line = LocalizedStringVar(value='Сохранение не открыто. Можно выбрать файл вручную.')
        self.sidebar_file_var=LocalizedStringVar(value='saveXXX.dat')
        self.sidebar_path_var=LocalizedStringVar(value=tr('Путь не выбран'))
        self.sidebar_time_var=LocalizedStringVar(value='--.--.---- --:--')
        self.sidebar_state_var=LocalizedStringVar(value=tr('Файл не загружен'))
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
        self.only_missing.trace_add('write', lambda *_: self._on_presence_filter('missing'))
        self.only_present.trace_add('write', lambda *_: self._on_presence_filter('present'))
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
        self.bind('<Control-z>',lambda _e:self.undo())
        self.bind('<Delete>',self._delete_shortcut)
        self.bind('<Return>',self._apply_shortcut)
        self.bind('<Control-a>',self._select_all_shortcut)

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
        if hasattr(self,'_detail_images'):self._detail_images.clear()
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
            if hasattr(self,'_detail_images'):self._detail_images.clear()
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
        # Compute this once per catalog rebuild, not during each row render.
        scanned_items = self.scanned_catalog
        russian_names = sum(
            any('А' <= c <= 'я' or c in 'Ёё' for c in str(v.get('name', '')))
            for v in scanned_items.values()
        )
        is_russian_scan = (russian_names >= 20 and russian_names * 4 >= len(scanned_items))
        self._ru_scanned_names = {
            k for k, value in scanned_items.items()
            if is_russian_scan and not is_english_only(str(value.get('name', '')))
        }
        if hasattr(self, '_item_images'):
            self._item_images.clear()
        if hasattr(self,'_detail_images'):self._detail_images.clear()
        if hasattr(self, '_resolved_icon_paths'):
            self._resolved_icon_paths.clear()

    def apply_theme(self, save=False):
        """A single responsive, in-game-inspired cyan/steel palette."""
        p = {'bg':'#09283F', 'panel':'#07324C', 'surface':'#10445F',
             'fg':'#F1F9FF', 'muted':'#BDDCEB', 'input':'#062A41',
             'border':'#3589AD', 'select':'#0878B4', 'button':'#0D4765',
             'hover':'#156F99', 'disabled':'#82A6B6', 'accent':'#048EDD',
             'accent_hover':'#21B9F7', 'danger':'#FF9EAA', 'stripe':'#0C3954',
             'focus':'#80E9FF'}
        self.style.theme_use('clam')
        self.configure(background=p['bg'])
        self.style.configure('.', font=('Segoe UI', 10), background=p['bg'], foreground=p['fg'])
        for key,color in [('TFrame',p['bg']),('App.TFrame',p['bg']),
                          ('Card.TFrame',p['panel']),('Header.TFrame',p['panel']),
                          ('Nav.TFrame',p['input'])]:
            self.style.configure(key, background=color)
        self.style.configure('TLabel',background=p['bg'],foreground=p['fg'])
        self.style.configure('Card.TLabel',background=p['panel'],foreground=p['fg'])
        self.style.configure('Icon.TLabel',background='#092942',foreground=p['fg'])
        self.style.configure('CardMuted.TLabel',background=p['panel'],foreground=p['muted'])
        self.style.configure('Nav.TLabel',background=p['input'],foreground=p['fg'])
        self.style.configure('NavMuted.TLabel',background=p['input'],foreground=p['muted'])
        self.style.configure('Title.TLabel',background=p['panel'],foreground=p['fg'],font=('Cambria',22))
        self.style.configure('Section.TLabel',background=p['panel'],foreground=p['fg'],font=('Segoe UI Semibold',11))
        self.style.configure('Info.TLabel',background=p['bg'],foreground=p['muted'])
        self.style.configure('TButton',background=p['button'],foreground=p['fg'],bordercolor=p['border'],
                             padding=(10,7),relief='flat')
        self.style.map('TButton',background=[('disabled',p['input']),('pressed',p['select']),('active',p['hover'])],
                       foreground=[('disabled',p['disabled'])])
        self.style.configure('Accent.TButton',background=p['accent'],foreground='#FFFFFF',
                             bordercolor=p['focus'],relief='flat',padding=(10,8))
        self.style.map('Accent.TButton',background=[('active',p['accent_hover']),('pressed',p['select'])])
        self.style.configure('Danger.TButton',background=p['button'],foreground=p['danger'],
                             bordercolor=p['border'],relief='flat',padding=(10,8))
        self.style.map('Danger.TButton',background=[('active',p['hover'])])
        self.style.configure('Nav.TButton',background=p['input'],foreground=p['fg'],
                             borderwidth=0,relief='flat',anchor='w',padding=(14,11))
        self.style.map('Nav.TButton',background=[('active',p['hover'])])
        self.style.configure('ActiveNav.TButton',background=p['select'],foreground='#FFFFFF',
                             borderwidth=0,relief='flat',anchor='w',padding=(14,11))
        self.style.map('ActiveNav.TButton',background=[('active',p['select'])])
        self.style.configure('Nav.TButton',font=('Segoe UI Semibold',13))
        self.style.configure('ActiveNav.TButton',font=('Segoe UI Semibold',13))
        for style,background in [('TCheckbutton',p['bg']),('Card.TCheckbutton',p['panel'])]:
            self.style.configure(style,background=background,foreground=p['fg'])
            self.style.map(style,background=[('active',background)])
        for widget in ('TEntry','TSpinbox','TCombobox'):
            self.style.configure(widget,fieldbackground=p['input'],background=p['input'],
                                 foreground=p['fg'],bordercolor=p['border'],arrowcolor=p['fg'],
                                 insertcolor=p['fg'],padding=6)
            self.style.map(widget,fieldbackground=[('readonly',p['input']),('disabled',p['surface'])],
                           foreground=[('readonly',p['fg']),('disabled',p['disabled'])])
        self.style.configure('Game.TNotebook',background=p['bg'],borderwidth=0)
        # Navigation rail owns page switching, so no duplicate top tab strip.
        self.style.layout('Game.TNotebook.Tab',[])
        for style in ('Treeview','Category.Treeview'):
            self.style.configure(style,background=p['panel'],foreground=p['fg'],
                fieldbackground=p['panel'],borderwidth=0,rowheight=32,bordercolor=p['border'])
            self.style.map(style,background=[('selected',p['select'])],foreground=[('selected','#FFFFFF')])
        self.style.configure('Treeview.Heading',background=p['surface'],foreground=p['fg'],
                             bordercolor=p['border'],relief='flat',padding=(6,6),
                             font=('Segoe UI Semibold',10))
        self.style.map('Treeview.Heading',background=[('active',p['hover'])])
        self.style.configure('TScrollbar',background=p['button'],troughcolor=p['input'],arrowcolor=p['fg'])
        self.style.configure('TSeparator',background=p['border'])
        self._install_hud_button_skins()
        self.style.configure('Game.TLabelframe',background=p['panel'],bordercolor=p['border'])
        self.style.configure('Game.TLabelframe.Label',background=p['panel'],foreground=p['fg'],
                             font=('Segoe UI Semibold',11))
        if hasattr(self,'details'):
            self.details.configure(bg=p['input'],fg=p['fg'],insertbackground=p['fg'],
                                   highlightbackground=p['border'],selectbackground=p['select'],
                                   selectforeground='#FFFFFF')
        for tree in (getattr(self,'tree',None),getattr(self,'all_tree',None)):
            if tree:tree.tag_configure('stripe',background=p['stripe'])
        self._colors=p

    def _install_hud_button_skins(self):
        """Nine-slice glowing cyan/dark glass sprites for actual ttk buttons."""
        if getattr(self,'_hud_sprites',None):
            return
        try:
            from PIL import Image,ImageDraw,ImageTk
            self._hud_sprites={}
            def sprite(key,top,bottom,edge,shine,height=48):
                im=Image.new('RGBA',(166,height),(0,0,0,0));d=ImageDraw.Draw(im,'RGBA')
                for j in range(3,0,-1):
                    d.rounded_rectangle((j,j,165-j,height-1-j),radius=5,outline=(*edge,18+20*(4-j)),width=1)
                for y in range(4,height-4):
                    t=(y-4)/max(1,height-8)
                    col=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
                    d.line((4,y,161,y),fill=(*col,255))
                d.rounded_rectangle((3,3,162,height-4),radius=4,outline=(*edge,235),width=2)
                d.line((12,5,154,5),fill=(*shine,165),width=2)
                d.line((12,height-6,154,height-6),fill=(*edge,74),width=1)
                obj=ImageTk.PhotoImage(im,master=self)
                self._hud_sprites[key]=obj
                return obj
            normal=sprite('normal',(15,74,105),(6,41,68),(79,176,214),(167,232,249))
            nhover=sprite('nhover',(26,110,145),(7,60,87),(80,215,245),(196,243,255))
            active=sprite('accent',(20,165,236),(3,81,176),(96,238,255),(228,255,255))
            ahover=sprite('ahover',(42,193,252),(3,101,198),(117,249,255),(243,255,255))
            danger=sprite('danger',(74,43,65),(37,26,50),(212,88,116),(247,157,172))
            nav=sprite('nav',(10,47,73),(7,39,65),(35,109,142),(71,146,186))
            nav_active=sprite('navactive',(23,160,227),(3,77,150),(82,240,255),(226,255,255))
            normal_small=sprite('normal_small',(15,74,105),(6,41,68),(79,176,214),(167,232,249),height=39)
            hover_small=sprite('hover_small',(26,110,145),(7,60,87),(80,215,245),(196,243,255),height=39)
            active_small=sprite('accent_small',(20,165,236),(3,81,176),(96,238,255),(228,255,255),height=39)
            danger_small=sprite('danger_small',(74,43,65),(37,26,50),(212,88,116),(247,157,172),height=39)
            for name,base,hover in [('HUDGlass',normal,nhover),('HUDAccent',active,ahover),
                                    ('HUDDanger',danger,nhover),('HUDNav',nav,nhover),('HUDNavActive',nav_active,ahover),
                                    ('HUDCompact',normal_small,hover_small),('HUDCompactAccent',active_small,hover_small),
                                    ('HUDCompactDanger',danger_small,hover_small)]:
                self.style.element_create(name,'image',base,('active',hover),('pressed',hover),
                                          border=(12,12,12,12),sticky='nswe')
            for style,name in [('TButton','HUDGlass'),('Accent.TButton','HUDAccent'),
                               ('Danger.TButton','HUDDanger'),('Compact.TButton','HUDCompact'),
                               ('CompactAccent.TButton','HUDCompactAccent'),('CompactDanger.TButton','HUDCompactDanger'),
                               ('Nav.TButton','HUDNav'),
                               ('ActiveNav.TButton','HUDNavActive')]:
                self.style.layout(style,[(name,{'sticky':'nswe','children':[
                    ('Button.focus',{'sticky':'nswe','children':[
                        ('Button.padding',{'sticky':'nswe','children':[
                            ('Button.label',{'sticky':'nswe'})]})]})]})])
                self.style.configure(style,borderwidth=0,relief='flat',padding=(9,5))
        except (ImportError,tk.TclError,ValueError) as exc:
            # The simpler standard Windows ttk theme remains functional.
            self._hud_sprites=None

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
        """Working Tk interface matched to the approved cinematic game HUD.

        Background/ornaments are static artwork. Treeviews, search, filters and
        save actions remain live widgets rather than text flattened into an image.
        """
        from PIL import Image, ImageTk
        wall=Image.open(resource_path('assets/academy_hud_background.jpg')).convert('RGB')
        self._wall_original=wall
        self._wall_photo=ImageTk.PhotoImage(wall.resize((1620,910),Image.Resampling.BILINEAR),master=self)
        self._wall_label=tk.Label(self,image=self._wall_photo,bg=self._colors['bg'],bd=0)
        self._wall_label.place(x=0,y=0,relwidth=1,relheight=1)
        self._wall_label.lower()
        # Single resize update, not 1200 Treeview repaints per motion event.
        self._wall_job=None
        self.bind('<Configure>',self._resize_backdrop,add='+')

        # Cinematic translucent header: actual academy scenery is visible through
        # a precomposed glass layer. Labels are native Canvas text (not a bitmap).
        header=tk.Canvas(self,height=105,bg='#0A314D',highlightthickness=0,borderwidth=0)
        self.header_canvas=header
        header.pack(fill='x',pady=(0,0))
        header.pack_propagate(False)
        self._header_image_id=header.create_image(0,0,anchor='nw')
        self._header_title=header.create_text(172,40,anchor='w',text=tr('Редактор сохранений'),
                 fill='#F6FBFF',font=('Cambria',32))
        self._header_subtitle=header.create_text(174,81,anchor='w',
                 text='COLD STEEL III  ·  ИНВЕНТАРЬ',
                 fill='#84D4F4',font=('Cambria',12))
        lang=tk.Frame(header,bg='#103A59',padx=8,pady=7)
        lang_caption=tk.Label(lang,text=tr('Язык'),bg='#103A59',fg='#C9E4F2',
                 font=('Segoe UI',10))
        lang_caption._ru_ui_text='Язык'
        lang_caption.pack(side='left',padx=(0,9))
        self.language_combo=ttk.Combobox(lang,state='readonly',width=9,
              textvariable=self.language_var,values=('Русский','English'))
        self.language_combo.pack(side='left')
        self.language_combo.bind('<<ComboboxSelected>>',lambda _e:self.change_language())
        self._lang_window=header.create_window(0,26,window=lang,anchor='ne')
        def header_resize(e):
            if e.widget is header:
                header.coords(self._lang_window,max(100,e.width-28),26)
                if getattr(self,'_header_job',None):
                    try:self.after_cancel(self._header_job)
                    except tk.TclError:pass
                self._header_job=self.after(120,lambda w=e.width:self._redraw_header(w,105))
        header.bind('<Configure>',header_resize)
        # Main save operations remain prominent, one-line and always accessible.
        toolbar=tk.Frame(self,bg='#0C3551',height=79,highlightbackground='#2D8EB2',highlightthickness=0)
        toolbar.pack(fill='x',padx=(232,26),pady=(5,0))
        toolbar.pack_propagate(False)
        self._toolbar_photo=None
        self._toolbar_art=tk.Label(toolbar,bd=0,highlightthickness=0,bg='#0C3551')
        self._toolbar_art.place(x=0,y=0,relwidth=1,relheight=1)
        self._toolbar_art.lower()
        toolbar.bind('<Configure>',self._on_toolbar_resize)
        self.toolbar_buttons={
            'latest':ttk.Button(toolbar,text='▤  '+tr('Последнее сохранение')+'   F5',style='Accent.TButton',command=self.load_latest_save),
            'open':ttk.Button(toolbar,text='▣  '+tr('Открыть вручную')+'  Ctrl+O',command=self.open_save),
            'compare':ttk.Button(toolbar,text='⚖  '+tr('Сравнить два файла'),command=self.compare_saves),
            'copy':ttk.Button(toolbar,text='▣  '+tr('Сохранить копию…'),command=self.save_copy),
            'overwrite':ttk.Button(toolbar,text='▤  '+tr('Записать с резервной копией'),command=self.save_overwrite),
        }
        for k in ('latest','open','compare'):
            self.toolbar_buttons[k].pack(side='left',padx=(12,6) if k=='latest' else 6,pady=4)
        self.toolbar_buttons['copy'].pack(side='right',padx=(6,12),pady=4)
        self.toolbar_buttons['overwrite'].pack(side='right',padx=6,pady=4)
        self._toolbar_compact=None
        topline=tk.Frame(self,bg='#0C3551',height=23)
        topline.pack(fill='x',padx=(232,26),pady=(0,9))
        self.save_note=tk.Label(topline,textvariable=self.save_line,bg='#0C3551',fg='#D1E7F3',
                                font=('Segoe UI',9),anchor='w')
        self.save_note.pack(fill='x',padx=9,pady=2)

        # The status bar is visually separate from the content glass panels.
        foot=tk.Frame(self,bg='#092B44',height=32,highlightthickness=1,highlightbackground='#377F9E')
        foot.pack(side='bottom',fill='x',padx=(205,13),pady=(4,6))
        foot.pack_propagate(False)
        ttk.Label(foot,textvariable=self.status,style='Info.TLabel').pack(side='left',padx=10,pady=6)
        ttk.Label(foot,textvariable=self.catalog_status,style='Info.TLabel').pack(side='right',padx=10,pady=6)

        middle=tk.Frame(self,bg='#0A2A40')
        middle.pack(fill='both',expand=True,padx=(14,14),pady=(0,1))
        rail=tk.Frame(middle,bg='#0B304D',width=214,highlightbackground='#3A93B7',highlightthickness=0)
        rail.pack(side='left',fill='y',padx=(0,9))
        rail.pack_propagate(False)
        self.nav_buttons={}
        for key,title in (('inventory','◫  Инвентарь'),('catalog','▤  Каталог'),('tools','⚙  Инструменты')):
            button=ttk.Button(rail,text=tr(title),style='Nav.TButton',
                              command=lambda k=key:self.show_page(k))
            button.pack(fill='x',pady=(11 if key=='inventory' else 11,3),padx=5)
            self.nav_buttons[key]=button
        self.nav_mode_hint=tk.Label(rail,text='COLD STEEL III   ·   HUD',bg='#0B304D',fg='#81B6CE',font=('Cambria',9),anchor='center')
        self.nav_mode_hint.pack(fill='x',pady=(8,3))
        spacer=ttk.Frame(rail,style='Nav.TFrame')
        spacer.pack(fill='both',expand=True)
        rail_info=tk.Frame(rail,bg='#113B58',highlightbackground='#356F90',highlightthickness=1)
        rail_info.pack(fill='x',padx=10,pady=(0,12))
        tk.Label(rail_info,textvariable=self.sidebar_file_var,bg='#113B58',fg='#E7F5FF',font=('Segoe UI Semibold',10),anchor='w',justify='left').pack(fill='x',padx=10,pady=(10,2))
        tk.Label(rail_info,text='▣',bg='#113B58',fg='#9FD6EB',font=('Segoe UI',11),anchor='w').place(x=10,y=38)
        tk.Label(rail_info,textvariable=self.sidebar_path_var,bg='#113B58',fg='#B9DCE9',font=('Segoe UI',9),wraplength=168,justify='left',anchor='w').pack(fill='x',padx=(30,10),pady=(0,5))
        time_row=tk.Frame(rail_info,bg='#113B58')
        time_row.pack(fill='x',padx=10,pady=(0,4))
        tk.Label(time_row,text='◷',bg='#113B58',fg='#9FD6EB',font=('Segoe UI',10)).pack(side='left')
        tk.Label(time_row,textvariable=self.sidebar_time_var,bg='#113B58',fg='#B9DCE9',font=('Segoe UI',9)).pack(side='left',padx=(8,0))
        state_row=tk.Frame(rail_info,bg='#113B58')
        state_row.pack(fill='x',padx=10,pady=(0,10))
        tk.Label(state_row,text='●',bg='#113B58',fg='#8CE5BE',font=('Segoe UI',10)).pack(side='left')
        tk.Label(state_row,textvariable=self.sidebar_state_var,bg='#113B58',fg='#8CE5BE',font=('Segoe UI',9)).pack(side='left',padx=(8,0))

        self.work_area=ttk.Frame(middle,style='App.TFrame')
        self.work_area.pack(side='left',fill='both',expand=True)
        # Non-resizable detail panel, beveled cyan frame.
        self.right_panel=tk.Frame(self.work_area,bg='#3487AA',width=405)
        self.right_panel.pack(side='right',fill='y',padx=(10,0))
        self.right_panel.pack_propagate(False)
        right=ttk.Frame(self.right_panel,style='Card.TFrame',padding=(16,14,16,12))
        self.right_content=right
        right.pack(fill='both',expand=True,padx=2,pady=2)
        self._right_compact=False
        self.right_panel.bind('<Configure>', self._on_right_panel_resize, add='+')
        self._hud_corners_right=attach_corners(self.right_panel,bg='#07324C')
        self.main_panel=tk.Frame(self.work_area,bg='#3487AA')
        self.main_panel.pack(side='left',fill='both',expand=True)
        content=ttk.Frame(self.main_panel,style='Card.TFrame',padding=(8,7,8,7))
        content.pack(fill='both',expand=True,padx=2,pady=2)
        self._hud_corners_main=attach_corners(self.main_panel,bg='#07324C')
        # Reference screenshot's floating beveled tabs above one central frame.
        navtabs=ttk.Frame(content,style='Card.TFrame')
        self.mode_bar=navtabs
        navtabs.pack(fill='x',pady=(0,8))
        self.mode_buttons={}
        for key,text in (('catalog','Каталог предметов'),('inventory','Мой инвентарь')):
            b=HUDTab(navtabs,text=tr(text),command=lambda k=key:self.show_page(k))
            b.pack(side='left',padx=(0,4))
            self.mode_buttons[key]=b
        self.tabs=ttk.Notebook(content,style='Game.TNotebook')
        self.tabs.pack(fill='both',expand=True)
        page_all=ttk.Frame(self.tabs,style='Card.TFrame',padding=(3,2,3,2))
        page_inv=ttk.Frame(self.tabs,style='Card.TFrame',padding=(3,2,3,2))
        page_tools=ttk.Frame(self.tabs,style='Card.TFrame',padding=(3,2,3,2))
        self.tabs.add(page_all,text=tr('Каталог'))
        self.tabs.add(page_inv,text=tr('Инвентарь'))
        self.tabs.add(page_tools,text=tr('Инструменты'))
        self.page_names=('catalog','inventory','tools')

        # Inventory has an information panel like the reference's inventory mode.
        invpane=ttk.Frame(page_inv,style='Card.TFrame')
        invpane.pack(fill='both',expand=True)
        info=ttk.Frame(invpane,style='Card.TFrame',width=210,padding=8)
        info.pack(side='left',fill='y',padx=(0,10))
        info.pack_propagate(False)
        ttk.Label(info,text=tr('ИНФОРМАЦИЯ О СОХРАНЕНИИ'),style='Section.TLabel',wraplength=180).pack(anchor='w',pady=(4,12))
        ttk.Label(info,textvariable=self.save_line,style='CardMuted.TLabel',wraplength=185).pack(fill='x',pady=(0,20))
        for name,func in [(tr('Папка сохранений'),self.open_saves_folder),
                          (tr('Сохранить копию'),self.save_copy),
                          (tr('Сравнить файлы'),self.compare_saves)]:
            ttk.Button(info,text=name,command=func,style='Compact.TButton').pack(fill='x',pady=(0,9))
        invtable=ttk.Frame(invpane,style='Card.TFrame')
        invtable.pack(side='left',fill='both',expand=True)
        invsearch=tk.Frame(invtable,bg='#0B3B57',highlightbackground='#5CAED0',highlightthickness=1)
        invsearch.pack(fill='x',pady=(0,10))
        tk.Label(invsearch,text='⌕',bg='#0B3B57',fg='#D4F7FF',font=('Segoe UI Symbol',18)).pack(side='left',padx=(10,6),pady=4)
        self.inventory_search_entry=ttk.Entry(invsearch,textvariable=self.search_inv)
        self.inventory_search_entry.pack(side='left',fill='x',expand=True,pady=5)
        self._install_search_hint(self.inventory_search_entry,self.search_inv,
                                  'Поиск по названию, ID или описанию…')
        ttk.Button(invsearch,text='×',command=lambda:self.search_inv.set(''),width=3).pack(side='left',padx=(5,8),pady=4)
        invbar=ttk.Frame(invtable,style='Card.TFrame')
        invbar.pack(fill='x',pady=(0,9))
        ttk.Label(invbar,text=tr('Ctrl / Shift — выделение нескольких предметов'),
                  style='CardMuted.TLabel').pack(side='left')
        ttk.Button(invbar,text=tr('Удалить выбранные'),style='Danger.TButton',
                   command=self.delete_bulk_selected).pack(side='right')
        self.tree=self._new_tree(invtable,[('slot','Слот',52),('id','ID',68),('qty','Кол-во',78)],
                                 icons=True,name_width=220,sort_kind='inventory',multi=True)
        self.tree.bind('<<TreeviewSelect>>',lambda _e:self._select_from_tree(self.tree))
        self.tree.bind('<Double-1>',lambda _e:self._focus_qty())

        # Catalog: same two-column silhouette as the reference art.
        pane=ttk.Frame(page_all,style='Card.TFrame')
        pane.pack(fill='both',expand=True)
        cat=ttk.Frame(pane,style='Card.TFrame',width=252,padding=(4,4,4,4))
        cat.pack(side='left',fill='y',padx=(0,10))
        cat.pack_propagate(False)
        treewrap=ttk.Frame(cat,style='Card.TFrame')
        treewrap.pack(fill='both',expand=True)
        self.category_tree=ttk.Treeview(treewrap,show='tree',style='Category.Treeview',selectmode='browse')
        self.category_tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(treewrap,command=self.category_tree.yview)
        scroll.pack(side='right',fill='y')
        self.category_tree.configure(yscrollcommand=scroll.set)
        self.category_tree.column('#0',width=244,stretch=True)
        self.category_tree.bind('<<TreeviewSelect>>',self._on_category_change)
        table=ttk.Frame(pane,style='Card.TFrame')
        table.pack(side='left',fill='both',expand=True)
        searchrow=tk.Frame(table,bg='#0B3B57',highlightbackground='#5CAED0',highlightthickness=1)
        searchrow.pack(fill='x',pady=(0,9))
        tk.Label(searchrow,text='⌕',bg='#0B3B57',fg='#D4F7FF',font=('Segoe UI Symbol',18)).pack(side='left',padx=(10,6),pady=4)
        self.catalog_search_entry=ttk.Entry(searchrow,textvariable=self.search_all)
        self.catalog_search_entry.pack(side='left',fill='x',expand=True,pady=5)
        self._install_search_hint(self.catalog_search_entry,self.search_all,
                                  'Поиск по названию, ID или описанию…')
        ttk.Button(searchrow,text='×',command=lambda:self.search_all.set(''),width=3).pack(side='left',padx=(5,8),pady=4)
        filters=ttk.Frame(table,style='Card.TFrame')
        filters.pack(fill='x',pady=(0,7))
        ttk.Checkbutton(filters,text=tr('Только отсутствующие'),variable=self.only_missing,
                        style='Card.TCheckbutton').pack(side='left',padx=(0,5))
        ttk.Checkbutton(filters,text=tr('Только имеющиеся'),variable=self.only_present,
                        style='Card.TCheckbutton').pack(side='left')
        self.source_combo=ttk.Combobox(filters,textvariable=self.catalog_source,values=(
                     'Все источники','Основная игра','DLC'),state='readonly',width=14)
        self.source_combo.pack(side='right',padx=(0,6))
        self.source_combo.bind('<<ComboboxSelected>>',lambda _e:self.refresh_catalog())
        bulkbar=ttk.Frame(table,style='Card.TFrame')
        ttk.Label(bulkbar,text=tr('Ctrl / Shift — выбрать несколько'),style='CardMuted.TLabel').pack(side='left')
        self.bulk_button=ttk.Button(bulkbar,text=tr('Добавить выбранные предметы'),
                                    command=self.apply_bulk_change,style='Accent.TButton')
        self.bulk_button.pack(side='right')
        ttk.Button(bulkbar,text=tr('Добавить по 1'),command=self.add_one_each).pack(side='right',padx=(0,6))
        self.all_tree=self._new_tree(table,[('id','ID',62),('type','Категория',115),('qty','В сумке',72)],
                                     icons=True,name_width=190,sort_kind='catalog',multi=True)
        bulkbar.pack(fill='x',pady=(8,0))
        self.all_tree.bind('<<TreeviewSelect>>',lambda _e:self._select_from_tree(self.all_tree))
        self.all_tree.bind('<Double-1>',lambda _e:self._focus_qty())
        self._populate_categories()
        self._update_sort_headers('inventory')
        self._update_sort_headers('catalog')

        # Fixed right panel with a larger original icon and direct edit actions.
        ttk.Label(right,text=tr('ВЫБРАННЫЙ ПРЕДМЕТ'),style='Section.TLabel').pack(anchor='w',pady=(0,10))
        iconheader=ttk.Frame(right,style='Card.TFrame')
        self._right_iconheader=iconheader
        iconheader.pack(fill='x',pady=(0,13))
        icon_back=tk.Frame(iconheader,bg='#092942',width=88,height=88,
                      highlightbackground='#368DB6',highlightthickness=1)
        self._right_icon_back=icon_back
        icon_back.pack(side='left',padx=(0,14),pady=5)
        icon_back.pack_propagate(False)
        self.selected_icon_label=ttk.Label(icon_back,style='Icon.TLabel',anchor='center')
        self.selected_icon_label.pack(fill='both',expand=True,padx=4,pady=4)
        self.selected_name_var=LocalizedStringVar(value='Выберите предмет')
        self.selected_category_var=LocalizedStringVar(value='')
        itemidentity=ttk.Frame(iconheader,style='Card.TFrame')
        itemidentity.pack(side='left',fill='x',expand=True)
        ttk.Label(itemidentity,textvariable=self.selected_name_var,style='Card.TLabel',
                  wraplength=240,font=('Segoe UI Semibold',15)).pack(anchor='w',pady=(7,7))
        ttk.Label(itemidentity,textvariable=self.selected_category_var,
                  style='CardMuted.TLabel',wraplength=230).pack(anchor='w')
        self._hud_identity_rule=tk.Canvas(right,height=9,bg='#07324C',highlightthickness=0,bd=0)
        self._hud_identity_rule.pack(fill='x',pady=(0,5))
        self._hud_identity_rule.bind('<Configure>',self._paint_rule)
        values=ttk.Frame(right,style='Card.TFrame')
        self._right_values=values
        values.pack(fill='x',pady=(0,8))
        col1=ttk.Frame(values,style='Card.TFrame'); col1.pack(side='left',fill='x',expand=True,padx=(0,8))
        col2=ttk.Frame(values,style='Card.TFrame'); col2.pack(side='left',fill='x',expand=True)
        ttk.Label(col1,text=tr('ID предмета'),style='CardMuted.TLabel').pack(anchor='w')
        ttk.Entry(col1,textvariable=self.item_var,width=9).pack(fill='x',pady=(4,0))
        ttk.Label(col2,text=tr('Количество (0–99)'),style='CardMuted.TLabel').pack(anchor='w')
        self.qty_entry=ttk.Spinbox(col2,from_=0,to=MAX_QUANTITY,textvariable=self.qty_var,width=8)
        self.qty_entry.pack(fill='x',pady=(4,0))
        self._right_apply_button=ttk.Button(right,text='✓  '+tr('Применить количество'),style='CompactAccent.TButton',
                   command=self.apply_change)
        self._right_apply_button.pack(fill='x',pady=(8,6))
        self._right_delete_button=ttk.Button(right,text='▤  '+tr('Удалить предмет из сохранения'),style='CompactDanger.TButton',
                   command=self.delete_selected)
        self._right_delete_button.pack(fill='x',pady=(0,9))
        actions=ttk.Frame(right,style='Card.TFrame')
        self._right_actions=actions
        actions.pack(fill='x')
        ttk.Button(actions,text='↶  '+tr('Отменить'),style='Compact.TButton',command=self.undo).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(actions,text=tr('Сбросить правки'),style='Compact.TButton',command=self.revert).pack(side='left',fill='x',expand=True)
        self._hud_details_rule=tk.Canvas(right,height=10,bg='#07324C',highlightthickness=0,bd=0)
        self._hud_details_rule.pack(fill='x',pady=(12,7))
        self._hud_details_rule.bind('<Configure>',self._paint_rule)
        ttk.Label(right,text=tr('ОПИСАНИЕ И ХАРАКТЕРИСТИКИ'),style='Section.TLabel').pack(anchor='w',pady=(0,9))
        descwrap=ttk.Frame(right,style='Card.TFrame')
        descwrap.pack(fill='both',expand=True)
        self.details=tk.Text(descwrap,height=10,width=26,wrap='word',state='disabled',
            borderwidth=1,relief='solid',padx=13,pady=12,font=('Cambria',12),spacing2=5)
        self.details.pack(side='left',fill='both',expand=True)
        descscroll=ttk.Scrollbar(descwrap,command=self.details.yview)
        descscroll.pack(side='right',fill='y')
        self.details.configure(yscrollcommand=descscroll.set)
        self._make_tools_page(page_tools)
        self._update_sidebar_save_info()
        self.show_page('catalog')
        self._describe(None)
        self.apply_theme(save=False)

    def _on_right_panel_resize(self,event):
        """Reserve space for item descriptions on compact Windows displays.

        Only adjust fixed paddings when crossing a height threshold. Changing
        these on every motion event previously caused unnecessary relayouts.
        """
        if event.widget is not self.right_panel:return
        compact=(event.height < 570)
        if compact==self._right_compact:return
        self._right_compact=compact
        self.right_content.configure(padding=(12,7,12,5) if compact else (16,14,16,12))
        self._right_icon_back.configure(width=69 if compact else 88,
                                        height=69 if compact else 88)
        self._right_icon_back.pack_configure(pady=1 if compact else 5,
                                             padx=(0,9 if compact else 14))
        self._right_iconheader.pack_configure(pady=(0,3 if compact else 13))
        self._hud_identity_rule.pack_configure(pady=(0,1 if compact else 5))
        self._right_values.pack_configure(pady=(0,3 if compact else 8))
        self._right_apply_button.pack_configure(pady=(2,3) if compact else (8,6))
        self._right_delete_button.pack_configure(pady=(0,3 if compact else 9))
        self._hud_details_rule.pack_configure(pady=(5,3) if compact else (12,7))

    def _paint_rule(self,event):
        """Resizable etched cyan divider; redraw only when its canvas resizes."""
        if event.widget not in (getattr(self,'_hud_details_rule',None),getattr(self,'_hud_identity_rule',None)):
            return
        c=event.widget
        width=max(1,event.width)
        c.delete('all')
        if width>18:
            c.create_line(0,4,width,4,fill='#3185A9',width=1)
            c.create_line(14,3,width-14,3,fill='#7DCFEA',width=1)
            c.create_line(0,6,width,6,fill='#061D34',width=1)
            for x in (5,width-6):c.create_oval(x-2,2,x+2,6,fill='#81DEFF',outline='')

    def _update_toolbar_labels(self,width,force=False):
        """Compact headings only when necessary; preserve all five actions."""
        compact=width<1160
        if compact == getattr(self,'_toolbar_compact',None) and not force:return
        self._toolbar_compact=compact
        if compact:
            labels=(
                ('latest','▤  '+tr('Последнее сохранение')+'  F5'),
                ('open','▣  '+tr('Открыть вручную')),
                ('compare','⚖  '+tr('Сравнить два файла')),
                ('overwrite','▤  '+('Overwrite + backup' if self.language=='en' else 'Записать + копия')),
                ('copy','▣  '+tr('Сохранить копию')),
            )
        else:
            labels=(
                ('latest','▤  '+tr('Последнее сохранение')+'   F5'),
                ('open','▣  '+tr('Открыть вручную')+'  Ctrl+O'),
                ('compare','⚖  '+tr('Сравнить два файла')),
                ('overwrite','▤  '+tr('Записать с резервной копией')),
                ('copy','▣  '+tr('Сохранить копию…')),
            )
        for k,label in labels:
            self.toolbar_buttons[k].configure(text=label)

    def _on_toolbar_resize(self,event):
        """Toolbar glass is redrawn only on resize, never on pointer movement."""
        if event.widget is not getattr(self,'_toolbar_art',None).master:
            return
        self._update_toolbar_labels(event.width)
        if getattr(self,'_toolbar_job',None):
            try:self.after_cancel(self._toolbar_job)
            except tk.TclError:pass
        width=max(1,event.width);height=max(1,event.height)
        self._toolbar_job=self.after(120,lambda:self._paint_toolbar(width,height))

    def _paint_toolbar(self,width,height):
        self._toolbar_job=None
        try:
            from PIL import ImageTk
            if not self.winfo_exists():return
            image=strip(self._wall_original,width,height,405,darkness=152)
            self._toolbar_photo=ImageTk.PhotoImage(image,master=self)
            self._toolbar_art.configure(image=self._toolbar_photo)
            self._toolbar_art.lower()
        except (ImportError,tk.TclError):pass

    def _install_search_hint(self, entry, value, message):
        """A real placeholder label, never inserted into the search data model."""
        hint=tk.Label(entry,text=tr(message),fg='#8EBCD1',bg='#062A41',
                font=('Segoe UI',10),anchor='w',cursor='xterm')
        hint._ru_ui_text=message
        def update(*_):
            try:
                if value.get() or entry.focus_get()==entry:
                    hint.place_forget()
                else:
                    hint.place(x=13,rely=.5,anchor='w')
            except tk.TclError:
                pass
        hint.bind('<Button-1>',lambda _e:(entry.focus_set(),update()))
        entry.bind('<FocusIn>',lambda _e:update(),add='+')
        entry.bind('<FocusOut>',lambda _e:update(),add='+')
        value.trace_add('write',update)
        self.after_idle(update)
        return hint

    def _redraw_header(self,width,height):
        self._header_job=None
        """A cached, softly translucent image. Never reconstruct catalog widgets."""
        try:
            from PIL import ImageTk
            if width<=0:return
            image=strip(self._wall_original,width,height,260,darkness=123)
            self._header_photo=ImageTk.PhotoImage(image,master=self)
            self.header_canvas.itemconfigure(self._header_image_id,image=self._header_photo)
            self.header_canvas.tag_lower(self._header_image_id)
        except (ImportError,tk.TclError):
            pass

    def _resize_backdrop(self,event):
        if event.widget is not self or not hasattr(self,'_wall_original'):
            return
        if getattr(self,'_wall_job',None):
            try:self.after_cancel(self._wall_job)
            except tk.TclError:pass
        width,height=max(1,event.width),max(1,event.height)
        self._wall_job=self.after(145,lambda w=width,h=height:self._apply_wallpaper(w,h))

    def _apply_wallpaper(self,width,height):
        self._wall_job=None
        if not self.winfo_exists():return
        from PIL import Image,ImageTk
        self._wall_photo=ImageTk.PhotoImage(self._wall_original.resize((width,height),Image.Resampling.BILINEAR),master=self)
        self._wall_label.configure(image=self._wall_photo)
        self._wall_label.lower()

    def _make_tools_page(self, page):
        ttk.Label(page,text='ИНСТРУМЕНТЫ И ДИАГНОСТИКА',style='Section.TLabel').pack(anchor='w',pady=(0,10))
        wrapper=ttk.Frame(page,style='Card.TFrame')
        wrapper.pack(fill='both',expand=True)
        cv=tk.Canvas(wrapper,background=self._colors['panel'],highlightthickness=0,borderwidth=0)
        bar=ttk.Scrollbar(wrapper,orient='vertical',command=cv.yview)
        cv.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y')
        cv.pack(side='left',fill='both',expand=True)
        inside=ttk.Frame(cv,style='Card.TFrame',padding=(6,5,10,8))
        ident=cv.create_window((0,0),window=inside,anchor='nw')
        inside.bind('<Configure>',lambda _e:cv.configure(scrollregion=cv.bbox('all')))
        cv.bind('<Configure>',lambda e:cv.itemconfigure(ident,width=e.width))
        inside.columnconfigure(0,weight=1)
        inside.columnconfigure(1,weight=1)
        self.tools_frame=inside
        def group(title,items,row,col):
            box=ttk.LabelFrame(inside,text=title,style='Game.TLabelframe',padding=(11,11,11,9))
            box.grid(row=row,column=col,sticky='nsew',padx=5,pady=5)
            for label,fn in items:
                ttk.Button(box,text=label,command=fn,style='Compact.TButton').pack(fill='x',pady=(0,5))
            return box
        group('Сохранения',[
            ('Последнее сохранение',self.load_latest_save),
            ('Открыть вручную',self.open_save),
            ('Открыть папку сохранений',self.open_saves_folder),
            ('Открыть резервную копию (.bak)',self.open_backup),
            ('Сравнить два файла',self.compare_saves),
            ('Сохранить копию',self.save_copy),
            ('Записать + резервная копия',self.save_overwrite),
        ],0,0)
        group('Игра и каталоги',[
            ('Выбрать папку игры',self.choose_game_folder),
            ('Указать папку сохранений',self.choose_save_folder),
            ('Сканировать игру и DLC',lambda:self.start_scan(manual=True)),
            ('Импорт таблицы TBL / CSV',self.open_catalog),
            ('Импорт английской таблицы',self.import_english_catalog),
            ('Экспорт каталога в CSV',lambda:self.export_catalog_csv('catalog')),
            ('Экспорт инвентаря в CSV',lambda:self.export_catalog_csv('inventory')),
        ],0,1)
        group('Оригинальные иконки',[
            ('Скачать отсутствующие иконки',lambda:self.start_icon_download(manual=True)),
            ('Импорт PNG из папки',self.choose_icon_folder),
            ('Обновить индекс иконок',self.refresh_icons),
            ('Отчёт об отсутствующих PNG',self.show_missing_icon_report),
        ],1,0)
        group('Проверка данных',[
            ('Диагностика каталога',self.show_diagnostics),
            ('Отчёт о переводах DLC',self.export_missing_translations),
            ('Импорт переводов DLC',self.import_ru_dlc_translations),
        ],1,1)
        settings=group('Настройки',[],2,0)
        ttk.Checkbutton(settings,text='Автовыбор последнего сохранения',
                        variable=self.auto_latest,style='Card.TCheckbutton',
                        command=self._on_auto_change).pack(anchor='w',pady=4)
        ttk.Label(settings,text='Язык: Русский / English — переключатель в заголовке',
                  style='CardMuted.TLabel',wraplength=330).pack(anchor='w',pady=4)
        ttk.Label(settings,text='Оформление: игровая тема (единственная)',
                  style='CardMuted.TLabel').pack(anchor='w',pady=4)
        information=group('Состояние ресурсов',[],2,1)
        self.scan_button=ttk.Button(information,text='Повторить сканирование',
                            command=lambda:self.start_scan(manual=True))
        self.scan_button.pack(fill='x',pady=(0,5))
        self.icons_button=ttk.Button(information,text='Загрузить игровые иконки',
                            command=lambda:self.start_icon_download(manual=True))
        self.icons_button.pack(fill='x',pady=(0,5))
        ttk.Label(information,textvariable=self.scan_info,style='CardMuted.TLabel',
                  wraplength=360).pack(anchor='w',pady=(2,7))
        ttk.Label(information,textvariable=self.icon_status,style='CardMuted.TLabel',
                  wraplength=360).pack(anchor='w')

    def show_page(self,key):
        target={'catalog':0,'inventory':1,'tools':2}[key]
        self.tabs.select(target)
        for name,button in self.nav_buttons.items():
            button.configure(style='ActiveNav.TButton' if name==key else 'Nav.TButton')
        for tab_key,button in getattr(self,'mode_buttons',{}).items():
            button.set_active(key==tab_key)
        if key=='tools':
            self.mode_bar.pack_forget()
        elif not self.mode_bar.winfo_manager():
            self.mode_bar.pack(fill='x',pady=(0,8),before=self.tabs)
        if key=='tools':
            self.right_panel.pack_forget()
        elif not self.right_panel.winfo_manager():
            self.right_panel.pack(side='right',fill='y',padx=(10,0))

    def add_one_each(self):
        self.qty_var.set('1')
        self.apply_bulk_change()

    def _focus_qty(self):
        self.qty_entry.focus_set()
        self.qty_entry.selection_range(0,'end')

    def _on_presence_filter(self,which):
        if which=='missing' and self.only_missing.get():self.only_present.set(False)
        if which=='present' and self.only_present.get():self.only_missing.set(False)
        if hasattr(self,'all_tree'):self.refresh_catalog()

    def toggle_tools(self):
        self.show_page('catalog' if self.tabs.select()==str(self.tabs.tabs()[2]) else 'tools')

    def change_language(self):
        self.language='en' if self.language_var.get()=='English' else 'ru'
        set_language(self.language)
        self.settings['language']=self.language
        try:save_settings(self.settings)
        except OSError:pass
        self._translate_widgets(self)
        self.source_combo['values']=(tr('Все источники'),tr('Основная игра'),'DLC')
        if self.catalog_source.get() in ('Все источники','All sources'):
            self.catalog_source.set(tr('Все источники'))
        elif self.catalog_source.get() in ('Основная игра','Base game'):
            self.catalog_source.set(tr('Основная игра'))
        for index,name in enumerate(('Каталог','Инвентарь','Инструменты')):
            self.tabs.tab(index,text=tr(name))
        for label,(key,button) in zip(('◫  Инвентарь','▤  Каталог','⚙  Инструменты'),self.nav_buttons.items()):
            button.configure(text=tr(label))
        if hasattr(self,'toolbar_buttons'):
            self._update_toolbar_labels(self._toolbar_art.winfo_width(),force=True)
        if hasattr(self,'header_canvas'):
            self.header_canvas.itemconfigure(self._header_title,text=tr('Редактор сохранений'))
            self.header_canvas.itemconfigure(self._header_subtitle,text=('COLD STEEL III  ·  INVENTORY' if self.language=='en' else 'COLD STEEL III  ·  ИНВЕНТАРЬ'))
        for key,label in (('catalog','Каталог предметов'),('inventory','Мой инвентарь')):
            if key in getattr(self,'mode_buttons',{}): self.mode_buttons[key].set_text(tr(label))
        for var in (self.icon_status,self.scan_info,self.save_line,self.status,
                    self.catalog_status,self.selected_name_var,self.selected_category_var,
                    self.sidebar_file_var,self.sidebar_path_var,self.sidebar_time_var,self.sidebar_state_var):
            var.relocalize()
        self._update_sort_headers('inventory')
        self._update_sort_headers('catalog')
        self._populate_categories()
        self._refresh()
        self._describe(self.selected_item)
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

    def _persist_quicklists(self):
        self.settings['favorites']=sorted(self.favorites)
        self.settings['recents']=self.recents[:20]
        try:save_settings(self.settings)
        except OSError:pass

    def _remember_items(self,ids):
        for item_id in ids:
            if item_id in self.recents:self.recents.remove(item_id)
            self.recents.insert(0,item_id)
        self.recents=self.recents[:20]
        self._persist_quicklists()
        self._populate_categories()

    def toggle_favorite(self):
        selected=[int(v[3:]) for v in self.all_tree.selection() if v.startswith('all')]
        if not selected and self.selected_item is not None:selected=[self.selected_item]
        if not selected:
            messagebox.showinfo('Избранное','Сначала выберите предмет в каталоге.')
            return
        for item_id in selected:
            if item_id in self.favorites:self.favorites.remove(item_id)
            else:self.favorites.add(item_id)
        self._persist_quicklists()
        self._populate_categories()
        self.refresh_catalog()

    def delete_bulk_selected(self):
        if not self._require_save():return
        ids=sorted({int(v[3:]) for v in self.tree.selection() if v.startswith('inv')})
        if not ids:
            messagebox.showinfo('Выбор предметов','Выделите один или несколько предметов.')
            return
        if not messagebox.askyesno('Удаление',f'Удалить выбранные предметы ({len(ids)}) из сохранения?'):
            return
        assert self.save is not None
        snapshot=self.save.bytes()
        try:
            self.save.set_quantities({item_id:0 for item_id in ids})
            self._history.append(snapshot)
            self._history=self._history[-40:]
            self._refresh()
        except (ValueError,SaveFormatError) as exc:
            self.save._data=bytearray(snapshot)
            messagebox.showerror('Не удалось удалить выбранные предметы',str(exc))

    def choose_save_folder(self):
        folder=filedialog.askdirectory(title='Выберите папку сохранений',mustexist=True,
                         initialdir=self.settings.get('save_directory') or str(Path.home()))
        if folder:
            self.settings['save_directory']=str(Path(folder).resolve())
            try:save_settings(self.settings)
            except OSError as exc:messagebox.showerror('Настройки',str(exc))

    def open_backup(self):
        if self.save and self.save.changed and not messagebox.askyesno(
                  'Несохранённые изменения','Открыть резервную копию и потерять текущие правки?'):
            return
        file=filedialog.askopenfilename(title='Открыть резервную копию',
                filetypes=[('Резервные копии','*.bak*'),('Все файлы','*.*')],
                initialdir=self.settings.get('save_directory') or str(Path.home()))
        if not file:return
        try:
            backup=Path(file).resolve()
            loaded=CS3Save.from_file(backup)
            self._accept_save(backup,loaded)
            messagebox.showinfo('Резервная копия','Копия открыта. Для восстановления используйте «Сохранить копию» с именем saveXXX.dat.')
        except (OSError,ValueError) as exc:
            messagebox.showerror('Резервная копия',str(exc))

    def open_saves_folder(self):
        folders=save_directories(self.settings.get('save_directory'))
        directory=self.source.parent if self.source else next((p for p in folders if p.is_dir()),None)
        if directory is None:
            messagebox.showinfo('Сохранения','Папка сохранений не найдена. Откройте файл вручную.')
            return
        if os.name=='nt':
            os.startfile(str(directory))
        else:
            self._show_text('Папка сохранений',str(directory))

    def refresh_icons(self):
        self._item_images.clear()
        if hasattr(self,'_detail_images'):self._detail_images.clear()
        self._resolved_icon_paths.clear()
        self.refresh_catalog()
        self.refresh_inventory()
        self._describe(self.selected_item)
        self.icon_status.set(self._icon_status_text())

    def show_missing_icon_report(self):
        cache=icon_cache_dir()
        missing=sorted(n for n in ALL_ORIGINAL_FILES if not validate_file(cache/n))
        summary=f'Отсутствует оригинальных PNG: {len(missing)} из {len(ALL_ORIGINAL_FILES)}\n\n'
        self._show_text('Отчёт об отсутствующих PNG',summary+'\n'.join(missing))

    def _diagnostics_text(self):
        from collections import Counter
        valid=[(i,v) for i,v in self.catalog.items() if is_visible_item(v)]
        hidden=len(self.catalog)-len(valid)
        untranslated=[i for i,v in valid if not self._has_verified_ru_translation(i)
                      and i not in self.builtin and is_english_only(v.get('name',''))
                      and i not in KNOWN_RUSSIAN_DLC]
        missing_descriptions=[i for i,v in valid if not v.get('description')]
        ids=Counter(v.get('id',i) for i,v in self.catalog.items())
        duplicate=[k for k,count in ids.items() if count>1]
        missing_icons=sorted(n for n in ALL_ORIGINAL_FILES if not validate_file(icon_cache_dir()/n))
        return ('ДИАГНОСТИКА КАТАЛОГА\n\n'
                f'Всего записей: {len(self.catalog)}\n'
                f'Видимые: {len(valid)}\n'
                f'Скрытые технические записи: {hidden}\n'
                f'Предположительно отсутствует русский перевод: {len(untranslated)}\n'
                f'Без описания: {len(missing_descriptions)}\n'
                f'Повторяющихся внутренних ID: {len(duplicate)}\n'
                f'Не скачано игровых PNG: {len(missing_icons)}\n'
                '\nПредметы без русского перевода (ID):\n' + ', '.join(map(str,untranslated[:100])) +
                '\n\nОтсутствующие описания (ID):\n' + ', '.join(map(str,missing_descriptions[:100])) +
                '\n\nПримечание: проверка наличия PNG не подтверждает его визуальное соответствие предмету.')

    def show_diagnostics(self):
        self._show_text('Диагностика каталога',self._diagnostics_text())

    def export_catalog_csv(self,which):
        path=filedialog.asksaveasfilename(title='Экспорт данных в CSV',defaultextension='.csv',
             initialfile='CS3_inventory.csv' if which=='inventory' else 'CS3_catalog.csv',
             filetypes=[('CSV UTF-8','*.csv')])
        if not path:return
        if which=='inventory':
            entries=[(x.item_id,x.quantity) for x in self.save.items()] if self.save else []
        else:
            owned={x.item_id:x.quantity for x in self.save.items()} if self.save else {}
            entries=[(i,owned.get(i,0)) for i,v in self.catalog.items() if is_visible_item(v)]
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as stream:
                writer=csv.writer(stream)
                writer.writerow(['ID','Name','Category','Quantity','Description'])
                for item_id,qty in entries:
                    record=self.catalog.get(item_id,{})
                    writer.writerow([item_id,self._get_name(item_id),self._category_name(record),
                                     qty,clear_codes(self._get_description(item_id))])
            messagebox.showinfo('Экспорт каталога',f'Строк записано: {len(entries)}.\n{path}')
        except OSError as exc:
            messagebox.showerror('Экспорт каталога',str(exc))

    def _populate_categories(self):
        counts={key:0 for key in CATEGORY_NAMES}
        for item in self.catalog.values():
            if is_visible_item(item):
                counts[category_of(item)] += 1
        self.category_tree.delete(*self.category_tree.get_children())
        self.category_tree.insert('','end',iid='all',text=f'◈  {tr("Все предметы")}  ({sum(is_visible_item(v) for v in self.catalog.values())})')
        self.category_tree.insert('','end',iid='favorites',text=f'☆  {tr("Избранное")}  ({sum(item_id in self.favorites and is_visible_item(item) for item_id,item in self.catalog.items())})')
        self.category_tree.insert('','end',iid='recent',text=f'◷  {tr("Недавно добавленные")}  ({len([i for i in self.recents if i in self.catalog and is_visible_item(self.catalog[i])])})')
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

    def _update_sidebar_save_info(self):
        if self.source is None:
            self.sidebar_file_var.set('saveXXX.dat')
            self.sidebar_path_var.set(tr('Выберите папку с сохранением вручную'))
            self.sidebar_time_var.set('--.--.---- --:--')
            self.sidebar_state_var.set(tr('Файл не загружен'))
            return
        from datetime import datetime
        try:
            when=datetime.fromtimestamp(self.source.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
        except OSError:
            when='--.--.---- --:--'
        self.sidebar_file_var.set(self.source.name)
        self.sidebar_path_var.set(str(self.source.parent))
        self.sidebar_time_var.set(when)
        self.sidebar_state_var.set(tr('Файл загружен'))

    def _on_auto_change(self):
        self.settings['auto_latest']=self.auto_latest.get()
        try: save_settings(self.settings)
        except OSError as exc: messagebox.showerror('Настройки',str(exc))

    def destroy(self):
        """Cancel pending Tk timers before widgets and Tcl callbacks disappear."""
        pending=list(getattr(self,'_startup_jobs',[]))
        pending.append(getattr(self,'_wall_job',None))
        pending.append(getattr(self,'_header_job',None))
        pending.append(getattr(self,'_toolbar_job',None))
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

    def _delete_shortcut(self,event):
        # Delete inside an Entry should edit text, not erase an inventory item.
        if isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Spinbox,tk.Text)):
            return
        if self.tabs.select()==str(self.tabs.tabs()[1]):self.delete_bulk_selected()

    def _apply_shortcut(self,event):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Spinbox)):
            return
        if self.tabs.select()!=str(self.tabs.tabs()[2]):self.apply_change()

    def _select_all_shortcut(self,event):
        if event.widget in (getattr(self,'tree',None),getattr(self,'all_tree',None)):
            event.widget.selection_set(event.widget.get_children())
            return 'break'

    def focus_catalog_search(self, _event=None):
        self.show_page('catalog')
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
        self._update_sidebar_save_info()
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
            tree.insert('', 'end', iid=iid, text=('  '+text) if icon else text, image=icon,
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
            manual=resource_path('icons')
            from original_item_icons import original_icon_for_item
            original=original_icon_for_item(item_id,record,manual=manual)
            asset=original.path if original else None
            self._resolved_icon_paths[item_id]=asset
        if asset is None or not asset.is_file():
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

    def _detail_image(self,item_id):
        if item_id in self._detail_images:
            return self._detail_images[item_id]
        if item_id not in self._resolved_icon_paths:
            self._item_image(item_id)
        path=self._resolved_icon_paths.get(item_id)
        if path is None or not path.is_file():
            return ''
        try:
            from PIL import Image,ImageTk
            with Image.open(path) as raw:
                im=raw.convert('RGBA')
                im.thumbnail((76,76),Image.Resampling.LANCZOS)
                if max(im.size)<64:
                    im=im.resize((64,64),Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(im,master=self)
        except (OSError,tk.TclError,ImportError):
            return self._item_image(item_id)
        self._detail_images[item_id]=photo
        return photo

    def _has_verified_ru_translation(self, item_id):
        # Recognize a locally installed RU pack even when the text is Latin
        # in both languages (e.g. HP 1 / EP 1). No game text is bundled.
        override = self.user_overrides.get(item_id, {})
        if override.get('_locale') == 'ru':
            return True
        return item_id in self._ru_scanned_names

    def _get_name(self, item_id):
        if self.language == 'en':
            original = self.english_catalog.get(item_id)
            if original and original.get('name'):
                return original['name']
        fallback = self.catalog.get(item_id, {}).get('name')
        if fallback:
            if (self.language == 'ru' and item_id not in self.builtin
                    and not self._has_verified_ru_translation(item_id)
                    and is_english_only(fallback)):
                return '[EN] ' + fallback
            if self.language == 'en':
                # English-only GitHub builds can display the actual name as is.
                import re
                return '[RU] ' + fallback if re.search(r'[А-Яа-яЁё]',fallback) else fallback
            if (not self.builtin and item_id in self.english_catalog
                    and not self._has_verified_ru_translation(item_id)
                    and self.english_catalog[item_id].get('name') == fallback):
                # Russian translation was never imported; mark English text.
                return '[EN] ' + fallback
            return fallback
        return f'ID {item_id} {tr("(нет названия)")}'

    def _get_description(self, item_id):
        if self.language == 'en':
            original = self.english_catalog.get(item_id)
            if original is not None:
                return generated_help(original,'en') or original.get('description','')
            # A visibly marked fallback is safer than a fabricated translation.
            return '[Original English text not imported for this ID.]'
        if (not self.builtin and item_id in self.english_catalog
                and not self._has_verified_ru_translation(item_id)
                and self.catalog.get(item_id,{}).get('name') == self.english_catalog[item_id].get('name')):
            return '[Original Russian text not imported for this ID.]'
        desc = self.catalog.get(item_id, {}).get('description','')
        if is_english_only(desc) and not self._has_verified_ru_translation(item_id):
            return '[EN — нет русского перевода] ' + desc
        return desc

    def _category_name(self, item):
        return tr(CATEGORY_NAMES[category_of(item)])

    def _describe(self, item_id):
        if hasattr(self,'selected_name_var'):
            self.selected_name_var.set(self._get_name(item_id) if item_id is not None else 'Выберите предмет')
        if hasattr(self,'selected_icon_label'):
            icon=self._detail_image(item_id) if item_id is not None else ''
            self.selected_icon_label.configure(image=icon if icon else '',text='' if icon else '◇')
        item = self.catalog.get(item_id, {}) if item_id is not None else {}
        if hasattr(self,'selected_category_var'):
            self.selected_category_var.set(self._category_name(item) if item_id is not None else '')
        if item_id is None:
            content = tr('Выберите предмет в одной из вкладок, чтобы увидеть его описание.')
        else:
            content = clear_codes(self._get_description(item_id)) or tr('Нет описания в загруженной таблице.')
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
            if not is_visible_item(record) and item.item_id not in NON_INVENTORY_ITEM_IDS:continue
            french=record.get('fr','')
            if needle and not any(needle in str(z).casefold() for z in (str(item.item_id),name,french,record.get('name',''),self._get_description(item.item_id))):
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
            source=self.catalog_source.get()
            item_source=item.get('_source') or ('base' if item_id in self.builtin else 'unknown')
            if source in ('Основная игра','Base game') and item_source!='base':continue
            if source=='DLC' and item_source!='dlc':continue
            if self.active_category == 'favorites':
                if item_id not in self.favorites:continue
            elif self.active_category == 'recent':
                if item_id not in self.recents:continue
            elif not item_in_category(item,self.active_category):continue
            quantity=occupied.get(item_id,0)
            if filter_missing and quantity>0:continue
            if self.only_present.get() and quantity==0:continue
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
            self._remember_items([item_id])
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
            self._remember_items(changes)
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
        if self.source.suffix.lower()!='.dat':
            messagebox.showwarning('Резервная копия',
                 'Для резервной копии выберите «Сохранить копию» с расширением .dat.')
            return
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
