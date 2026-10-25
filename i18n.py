"""English UI vocabulary for the editor (no online translator required).

Game item text is *not* auto-translated: use a genuine English Falcom TBL,
indexed by stable item IDs.  This avoids inventing item names or effects.
"""
from __future__ import annotations
from tkinter import ttk as _ttk
import tkinter as tk
from tkinter import messagebox as _messagebox, filedialog as _filedialog

LANG = 'ru'

EN = {
    'COLD STEEL III  /  ИНВЕНТАРЬ': 'COLD STEEL III  /  INVENTORY',
    '  •  ВЕРСИЯ 6.0': '  •  VERSION 6.0',
    '  •  ВЕРСИЯ 6.1': '  •  VERSION 6.1',
    'Оформление': 'Appearance', 'Тёмная':'Dark', 'Светлая':'Light',
    'Последнее сохранение  F5':'Latest save  F5',
    'Открыть вручную  Ctrl+O':'Open manually  Ctrl+O',
    'Сравнить два файла':'Compare saves',
    'Сохранить копию…  Ctrl+S':'Save a copy…  Ctrl+S',
    'Записать с резервной копией':'Overwrite + backup',
    'Автовыбор при запуске':'Auto-open latest on startup',
    'Инструменты и игровые ресурсы  ▾':'Tools and game assets  ▾',
    'Скрыть инструменты  ▴':'Hide tools  ▴',
    'Сканировать игру и DLC':'Scan game and DLC',
    'Выбрать папку игры':'Select game folder',
    'Импорт .tbl / .csv':'Import .tbl / .csv',
    'Загрузить оригинальные иконки':'Download original icons',
    'Импорт папки PNG':'Import PNG folder',
    'Поддержка подарков и четырёх видов EX-сфер':'Gifts and four EX Orb types supported',
    'Каталог и добавление':'Item catalog',
    'Мой инвентарь':'My inventory',
    'Поиск предмета в сохранении':'Search inventory',
    'Выберите группу, затем предмет':'Choose a category and an item',
    'ГРУППЫ':'CATEGORIES', 'Очистить':'Clear',
    'Поиск по названию, ID или описанию':'Search by name, ID or description',
    'Показывать только отсутствующие':'Show missing items only',
    'ВЫБРАННЫЙ ПРЕДМЕТ':'SELECTED ITEM',
    'ID предмета':'Item ID', 'Количество':'Quantity',
    'Добавить / применить количество':'Add / update quantity',
    'Удалить предмет из сохранения':'Remove item from save',
    '↶ Отменить':'↶ Undo', 'Сбросить правки':'Discard changes',
    'Описание и характеристики':'Description and effects',
    'Изменения вносятся только в файл сохранения. Закройте игру перед записью.':
       'Changes only affect the save file. Close the game before writing.',
    'Предмет':'Item', 'Слот':'Slot', 'Кол-во':'Qty', 'Категория':'Category','В сумке':'Owned',
    'Кварцы':'Quartz','Обычные кварцы':'Standard quartz','Мастер-кварцы':'Master quartz',
    'Снаряжение':'Equipment','Оружие':'Weapons','Броня':'Armor','Обувь':'Footwear','Аксессуары':'Accessories',
    'Расходники и еда':'Consumables and food','Лечение и бой':'Healing and combat',
    'Готовые блюда':'Prepared dishes','Ингредиенты':'Ingredients',
    'Книги и рецепты':'Books and recipes','Рецепты':'Recipes','Книги и журналы':'Books and magazines',
    'Внешний вид':'Cosmetics','Костюмы':'Outfits','Аксессуары образа':'Cosmetic accessories',
    'Причёски':'Hairstyles','Декор и раскраски':'Decorations and colors',
    'Рыбалка':'Fishing','Рыба':'Fish','Удочки и снасти':'Rods and tackle',
    'Другие предметы':'Other items','Сюжетные и ключевые':'Quest and key items',
    'Материалы и сепит':'Materials and sepith','Карты и мини-игры':'Cards and minigames',
    'Сферы и улучшения':'EX Orbs and upgrades','Прочее':'Other',
    'Все предметы':'All items',
    'Оригинальные иконки:':'Original icons:', 'Мастер-кварцы:':'Master quartz:',
    'Загрузка игровых значков в кеш (редактор продолжает работать)…':
       'Downloading original icons in the background…',
    'Ошибок:':'Errors:', 'можно повторить загрузку.':'retry is available.',
    'Ошибки загрузки:':'Download errors:', 'Игровые значки':'Game icons',
    'Выберите папку с оригинальными PNG-иконками':'Select a folder with original PNG icons',
    'Импорт иконок':'Icon import','Импортировано файлов:':'Imported files:',
    'Пропущено повреждённых:':'Skipped invalid images:',
    'Копии сохранены отдельно от файлов игры.':'Copies are stored separately from game files.',
    'Поиск файлов предметов в папке игры и DLC…':'Scanning item tables in game and DLC folders…',
    'Папка игры не найдена автоматически. Укажите её кнопкой «Папка игры…».':
       'Could not locate the game automatically. Use Select game folder.',
    'Поиск игры':'Game discovery',
    'Steam-установка не найдена. Нажмите «Папка игры…» и выберите корневую папку Cold Steel III (где находится data).':
       'Could not locate the Steam installation. Select the Cold Steel III folder containing data.',
    'Не удалось прочитать таблицы; сохранённый каталог остался доступен.':
       'Could not read game tables; the cached catalog remains available.',
    'Сканирование':'Scan','Результаты сканирования':'Scan results',
    'Найдено таблиц:':'Tables found:',
    'Основных предметов:':'Base-game items:',
    'Новых уникальных предметов DLC:':'New unique DLC items:',
    'Всего найдено ID:':'Total IDs found:',
    'Ошибок таблиц:':'Table errors:',
    'Конфликтов ID:':'ID conflicts:',
    'Папка игры:':'Game directory:', 'Прочитанные таблицы:':'Parsed tables:',
    'Ошибки:':'Errors:', 'Конфликты ID (основная таблица имеет приоритет):':
       'ID conflicts (main table takes priority):',
    'Папка Cold Steel III (содержит каталог data)':'Cold Steel III game folder (contains data)',
    'Сканирование игры: ещё не выполнялось':'Game scan: not run yet',
    'Сканировано таблиц:':'Tables scanned:', 'из DLC добавлено:':'new DLC items:',
    'всего ID:':'total IDs:', 'есть ошибки':'errors occurred',
    'Настройки':'Settings',
    'Не удалось запомнить тему:':'Could not save theme:',
    'Не удалось сохранить каталог:':'Could not save catalog:',
    'Не удалось сохранить путь к игре:':'Could not save game directory:',
    'Сохранение не открыто. Можно выбрать файл вручную.':
       'No save loaded. You can open a file manually.',
    'Сохранение не открыто':'No save loaded',
    'Совместимые saveXXX.dat не найдены. Откройте сохранение вручную.':
       'No compatible saveXXX.dat files found. Open a save manually.',
    'Последнее сохранение':'Latest save','Загружено':'Loaded',
    'Пропущено некорректных файлов:':'Invalid files skipped:',
    'Автоматически выбрано':'Automatically selected','Открыто вручную':'Opened manually',
    'Несохранённые изменения':'Unsaved changes',
    'Есть правки, которые не были записаны в файл. Закрыть программу без сохранения?':
       'You have unsaved changes. Close without saving?',
    'Открыть последнее сохранение и потерять текущие правки?':
       'Open the latest save and discard unsaved changes?',
    'Открыть другое сохранение и потерять изменения?':
       'Open another save and discard unsaved changes?',
    'Неизвестный предмет':'Unknown item',
    'Неизвестный предмет #':'Unknown item #',
    '(нет названия)':'(name unavailable)',
    'Выберите предмет в одной из вкладок, чтобы увидеть его описание.':
       'Select an item from either tab to see its description.',
    'Категория:':'Category:', 'В инвентаре:':'In inventory:',
    'Нет описания в загруженной таблице.':'No description available in the loaded table.',
    'Изменения не записаны':'Unsaved changes', 'Без изменений':'No changes',
    'предметов в инвентаре':'items in inventory','Каталог:':'Catalog:',
    'названий':'names', 'предметов':'items','в выбранной группе:':'in selected category:',
    'встроенные + таблицы игры/DLC + дополнения':'built-in + game/DLC tables + imports',
    'Выберите предмет из каталога; для редактирования откройте saveXXX.dat':
       'Select an item from the catalog; open saveXXX.dat to edit its quantity.',
    'Встроенный каталог:':'Built-in catalog:',
    'Откройте сохранение':'Open a save',
    'Сначала откройте saveXXX.dat. Каталог доступен без сохранения.':
       'Open a saveXXX.dat first. You can browse the catalog without one.',
    'Открыть saveXXX.dat':'Open saveXXX.dat', 'Сохранения игры':'Game saves',
    'Все файлы':'All files','Не удалось открыть сохранение':'Failed to open save',
    'Не удалось изменить предмет':'Could not modify item',
    'отсутствует в каталоге. Он может быть недопустимым. Продолжить?':
       'is not present in the catalog and may be invalid. Continue?',
    'уже установлено количество':'already has quantity',
    'Нужен ID':'Item ID required','Выберите предмет в списке или введите ID':
       'Select an item or enter its ID.',
    'Удаление':'Remove item','Удалить ID':'Remove ID','из сохранения?':'from the save?',
    'Отмена':'Undo','Нет действий для отмены':'Nothing to undo',
    'Сброс изменений':'Discard changes','Отменить все изменения текущего сохранения?':
       'Discard all changes to the current save?',
    'Импорт новой таблицы или DLC':'Import item table or DLC','Таблицы предметов':'Item tables',
    'Импорт завершён':'Import complete','Ошибка импорта':'Import error',
    'Прочитано записей:':'Records read:','Новых ID:':'New IDs:',
    'Всего названий:':'Total names:',
    'Импорт сохранён для следующих запусков.':'Import saved for future sessions.',
    'Выберите ровно два файла':'Select exactly two files','Сохранения':'Saves',
    'Сравнение':'Comparison','Нужно выбрать ровно 2 файла (Ctrl + клик)':
       'Select exactly two files (Ctrl + click).',
    'Сравнение сохранений':'Save comparison','Ошибка сравнения':'Comparison error',
    'Добавлено':'Added', 'удалено':'removed','изменено':'modified',
    'Изменений за пределами инвентаря (байт):':'Changes outside inventory (bytes):',
    'Для записи оригинала используйте «Записать + backup»':
       'Use Overwrite + backup to update the original save.',
    'Файл существует':'File exists', 'Перезаписать':'Overwrite',
    'Файл был изменён вне редактора. Откройте его повторно.':
       'The save has changed externally. Please reopen it.',
    'Проверка записанного сохранения не пройдена':'Saved data verification failed',
    'Сохранить отдельную копию':'Save a separate copy','Файл сохранения':'Save file',
    'Копия записана':'Copy saved','Сохранено:':'Saved:',
    'Оригинал не изменён. Для загрузки в игре скопируйте файл под именем свободного слота saveXXX.dat.':
       'The original was not modified. To load it in-game, use an available saveXXX.dat slot.',
    'Не удалось сохранить':'Could not save',
    'Нет изменений':'No changes','Нет изменений для записи':'No changes to write',
    'Записать оригинал?':'Overwrite original?',
    'Закройте игру перед записью.':'Close the game before writing.',
    'Создаётся резервная копия .bak.':'A .bak backup will be created.',
    'Загрузка отредактированного файла игрой пока не проверена.':
       'Game-side compatibility of modified saves has not been verified.',
    'Записано':'Saved', 'Сохранение обновлено. Резервная копия создана.':
       'Save updated successfully. A backup was created.',
    'Ошибка записи':'Write error',
    'Оригинальный английский каталог':'Original English catalog',
    'Импорт английского .tbl':'Import English .tbl',
    'Английские названия':'English item names',
    'Английский файл не загружен':'No original English table loaded',
    'Русский':'Russian', 'Английский':'English',
    'Язык':'Language',
}
EN.update({
    '  •  ВЕРСИЯ 6.3': '  •  VERSION 6.3',
    'Ctrl / Shift — выбрать несколько предметов': 'Ctrl / Shift — select multiple items',
    'Добавить выбранные предметы': 'Add selected items',
    'Выбор предметов': 'Item selection',
    'Выделите предметы в каталоге. Используйте Ctrl или Shift для нескольких строк.':
        'Select catalog items. Use Ctrl or Shift to select multiple rows.',
    'Массовое добавление': 'Add multiple items',
    'Установить количество ': 'Set quantity ',
    ' для ': ' for ',
    ' предметов?': ' items?',
    'Новых предметов: ': 'New items: ',
    '. Уже имеющиеся будут изменены до ': '. Existing stacks will be set to ',
    'Количество должно быть от ': 'Quantity must be between ',
    'Недостаточно свободных слотов для выбранных предметов': 'Not enough free slots for the selected items',
    'У выбранных предметов уже установлено указанное количество.': 'All selected items already have the requested quantity.',
    'Выбрано предметов: ': 'Items selected: ',
    'Укажите общее количество и нажмите «Добавить выбранные предметы».':
        'Enter the quantity for all selected items and click Add selected items.',
    'Обновлено предметов: ': 'Updated items: ',
    '. Новых: ': '. Added: ',
    '. Изменения ещё не сохранены.': '. Changes have not been saved yet.',
    'Не удалось добавить выбранные предметы': 'Could not add selected items',
    'Отчёт о переводе DLC': 'DLC translation report',
    'Импорт перевода DLC': 'Import DLC translations',
    'Импорт перевода DLC (CSV из отчёта)': 'Import DLC translations (report CSV)',
    'Сохранить список непереведённых DLC': 'Save untranslated DLC report',
    'Непереведённых английских записей DLC не обнаружено.': 'No untranslated English DLC entries found.',
    'Переводы DLC': 'DLC translations',
    'Записей без проверенного русского перевода: ': 'Entries without a verified Russian translation: ',
    'Отчёт сохранён: ': 'Report saved: ',
    'Не удалось создать отчёт': 'Could not create report',
    'Нужны столбцы ID, Russian name, Russian description.':
        'The CSV must contain ID, Russian name and Russian description columns.',
    ': русский перевод названия отсутствует.': ': the Russian name is missing.',
    ': русский перевод описания отсутствует.': ': the Russian description is missing.',
    'В CSV нет заполненных переводов для известных предметов.': 'No translations for known items were found in the CSV.',
    'Загружено переводов: ': 'Translations imported: ',
    'Ошибка импорта перевода': 'Translation import error',
    'непереведённых DLC:': 'untranslated DLC:',
})

# Supplemental translations for parser/save diagnostics and dynamic UI states.
# Keep these messages separate from the official item catalog: game text must
# come from an original game .tbl, not from this UI vocabulary.
EN.update({
    'Доступный каталог:': 'Available catalog:',
    'Откройте сохранение вручную': 'Open a save manually',
    'Получены некорректные данные PNG': 'Invalid PNG data received',
    ' байт': ' bytes',
    ': для больших изображений и WebP необходим Pillow. Установите: py -3 -m pip install Pillow':
        ': Pillow is required for large images and WebP. Install: py -3 -m pip install Pillow',
    'HTML (возможно ограничение доступа Fandom)': 'HTML (possibly blocked by Fandom)',
    'Английский каталог не загружен. Импортируйте оригинальную таблицу через «Инструменты».':
        'No original English item catalog is loaded. Import one from Tools.',
    'Английский каталог импортирован': 'English catalog imported',
    'Ошибка импорта английского каталога': 'English catalog import failed',
    'Оригинальная английская таблица предметов (из игры без русификации)':
        'Original English item table (from an unmodified game)',
    'Таблица предметов': 'Item table',
    'Похоже, этот файл содержит русский перевод, а не оригинальную английскую таблицу.':
        'This file appears to contain Russian localization, not the original English item table.',
    'Загружено названий и описаний:': 'Names and descriptions imported:',
    'Всего английских записей:': 'Total English entries:',
    'Не удалось сохранить английский каталог:': 'Could not save the English catalog:',
    # Messages emitted by the binary .tbl reader and CSV/JSON importers.
    'CSV должен быть в кодировке UTF-8': 'The CSV file must use UTF-8 encoding',
    'TBL содержит неожиданное количество данных': 'Unexpected TBL record count or trailing data',
    'Названия предметов не найдены': 'No item names were found',
    'Конфликтующие названия для ID ': 'Conflicting item names for ID ',
    'Неверный UTF-8 для предмета ID ': 'Invalid UTF-8 in item ID ',
    'Неверный формат JSON-каталога': 'Invalid JSON catalog format',
    'Недопустимый тип записи в TBL': 'Invalid TBL record type',
    'Неизвестный тип записи: ': 'Unknown record type: ',
    'Некорректная длина записи TBL': 'Invalid TBL record length',
    'Некорректный ID в JSON-каталоге': 'Invalid item ID in JSON catalog',
    'Повреждена строка заголовка таблицы TBL': 'Corrupt TBL header string',
    'Повреждена таблица типов': 'Corrupt TBL group table',
    'Поддерживаются только .tbl и .csv': 'Only .tbl and .csv files are supported',
    'Пустое название в JSON-каталоге': 'Empty item name in JSON catalog',
    'Слишком короткая таблица TBL': 'TBL file is too short',
    'Файл обрывается перед записью TBL': 'TBL file ends before a complete record',
    'Это не t_item*.tbl: найдена таблица ': 'Not a t_item*.tbl file: found table ',
    'Не найдены строки CSV вида ID,Название[,Описание]':
        'No valid CSV rows found (expected: ID,Name[,Description])',
    'Это не таблица предметов Cold Steel III': 'Not a Cold Steel III item table',
    'Повреждена таблица типов': 'Corrupt TBL type table',
    'Количество записей в заголовке TBL не совпадает': 'TBL header record count does not match',
    'Неизвестный тип записи:': 'Unknown record type:',
    # Save parser: error text must use English even if the game save is invalid.
    'Размер ': 'File size ',
    ' байт вместо ожидаемых ': ' bytes; expected ',
    '. Редактор поддерживает проверенный тип сохранений CS3 NISA для Windows.':
        '. Only the verified Cold Steel III NISA Windows save format is supported.',
    'Неизвестная версия или тип файла сохранения': 'Unknown save-file format or version',
    'Длина в заголовке не совпадает с длиной файла': 'Save header length does not match file size',
    'Таблица предметов выходит за конец сохранения': 'Inventory table extends beyond the save file',
    'Неизвестные данные в записи инвентаря №': 'Unexpected data in inventory record #',
    '; запись отменена': '; operation cancelled',
    'Слот №': 'Slot #',
    ' помечен пустым, но содержит количество ': ' is marked empty but has quantity ',
    'Обнаружены предметы после пустых слотов — неизвестная структура инвентаря':
        'Items found after empty slots; unknown inventory layout',
    'Недопустимое количество ': 'Invalid quantity ',
    ' для ID ': ' for item ID ',
    ', слот ': ', slot ',
    'Дублирующийся ID ': 'Duplicate item ID ',
    ' — редактор остановлен': '; editing was stopped',
    'Не найдена достаточная область свободных слотов инвентаря':
        'Not enough free inventory slots could be verified',
    'ID предмета должен быть числом от 0 до 65535, кроме 9999':
        'Item ID must be between 0 and 65535, excluding 9999',
    'Количество должно быть в диапазоне ': 'Quantity must be between ',
    'Недостаточно свободных слотов для добавления': 'Not enough free inventory slots to add an item',
    # Discovery, image download and network diagnostics.
    'Таблица слишком большая': 'Item table exceeds the size limit',
    'Таблицы обнаружены, но прочитать ни одну не удалось:':
        'Item tables were found but none could be parsed:',
    'Выбранная папка не содержит таблиц предметов Cold Steel III.':
        'The selected folder does not contain Cold Steel III item tables.',
    'Нужна папка с каталогом data (корневая папка игры).':
        'Select the game root directory containing the data folder.',
    'Иконка не найдена в справочнике': 'Icon not found in the source index',
    'Не удалось получить список иконок:': 'Could not retrieve the icon index:',
    'Папка с иконками не найдена': 'Icon folder not found',
    'В папке слишком много изображений: выберите каталог с иконками':
        'Too many images in this folder; select an icon folder',
    'Недопустимое имя иконки': 'Invalid icon filename',
    'Слишком большой файл изображения': 'Image file exceeds the size limit',
    'Повреждённый PNG,': 'Corrupt PNG,',
    'Недоверенный адрес изображения': 'Untrusted image URL',
    'Недоверенный адрес миниатюры': 'Untrusted thumbnail URL',
    'Преобразование привело к недопустимому PNG':
        'Image conversion produced an invalid PNG',
    'Ответ сервера не является изображением:': 'Server response is not an image:',
    'Вместо изображения пришёл ': 'Received non-image response: ',
    'Ошибка MediaWiki API:': 'MediaWiki API error:',
    'Необычный размер изображения:': 'Unexpected image dimensions:',
    'Не удалось прочитать ': 'Could not read ',
    'Для больших изображений и WebP необходим Pillow. Установите:':
        'Pillow is required for large images and WebP. Install:',
    'пикселей, ': 'pixels, ',
    ' байт; сигнатура ': ' bytes; signature ',
    'неизвестные данные (': 'unknown data (',
    'Не удалось открыть папку ': 'Could not open folder ',
    ': несовместимый размер или файл обновляется':
        ': incompatible size or file is currently being updated',
    ': файл изменился во время чтения': ': file changed while reading',
    'Записать с резервной копией': 'Overwrite with backup',
})

# Exact matches first, then fragments (longest-first) for formatted status messages.
PHRASES = tuple(sorted(((k,v) for k,v in EN.items() if k),key=lambda pair:-len(pair[0])))

def set_language(value: str) -> None:
    global LANG
    LANG = 'en' if value == 'en' else 'ru'

def tr(text: str) -> str:
    if LANG != 'en' or not isinstance(text,str):
        return text
    if text in EN:
        return EN[text]
    for ru,en in PHRASES:
        text=text.replace(ru,en)
    return text


class LocalizedStringVar(tk.StringVar):
    """Translates status text at display time, retaining its Russian source."""
    def __init__(self, master=None, value='', name=None):
        super().__init__(master=master, name=name)
        self.set(value)
    def set(self,value):
        self.source=value
        super().set(tr(value) if isinstance(value,str) else value)
    def relocalize(self):
        if hasattr(self,'source'): self.set(self.source)


class _LocaleServices:
    def __init__(self, module): self.module=module
    def __getattr__(self, name):
        fn=getattr(self.module,name)
        if not callable(fn): return fn
        def wrapper(*args,**kwargs):
            args=tuple(tr(a) if isinstance(a,str) else a for a in args)
            kwargs={k:(tr(v) if isinstance(v,str) else
                      [(tr(a),b) for a,b in v] if k=='filetypes' else v)
                    for k,v in kwargs.items()}
            return fn(*args,**kwargs)
        return wrapper

messagebox=_LocaleServices(_messagebox)
filedialog=_LocaleServices(_filedialog)

# A lightweight ttk factory translates initial labels.  Widgets retain original
# source text so a language switch can redraw them without destroying panels.
class _Widgets:
    def __getattr__(self,name):
        cls=getattr(_ttk,name)
        if name not in {'Button','Label','Checkbutton','LabelFrame','Radiobutton'}:
            return cls
        def factory(*args,**kwargs):
            source=kwargs.get('text')
            if isinstance(source,str): kwargs['text']=tr(source)
            w=cls(*args,**kwargs)
            if isinstance(source,str): w._ru_ui_text=source
            return w
        return factory

ttk=_Widgets()

# Version is an explicit UI label, maintained for release builds.
EN.update({'  •  ВЕРСИЯ 7.0': '  •  VERSION 7.0'})
# Dynamic/fragment messages must include all later EN.update additions.
PHRASES = tuple(sorted(((k,v) for k,v in EN.items() if k), key=lambda pair: -len(pair[0])))
