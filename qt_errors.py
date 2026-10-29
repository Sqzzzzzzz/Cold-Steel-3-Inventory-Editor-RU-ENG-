"""Localized front-end errors without a dependency on the legacy Tk UI."""
import re

PAIRS={
    'CSV export cannot overwrite the opened save.':'Экспорт CSV не может перезаписать открытое сохранение.',
    'Choose a .csv file for inventory export.':'Для экспорта инвентаря выберите файл .csv.',
    'Open a compatible save first':'Сначала откройте совместимое сохранение',
    'Save not loaded':'Сохранение не загружено',
    'No save loaded':'Сохранение не загружено',
    'Use overwrite with backup for source file':'Для исходного файла используйте запись с резервной копией',
    'The destination exists. Pick a different filename.':'Файл уже существует. Выберите другое имя.',
    'The original save was modified after loading; write cancelled':'Исходное сохранение изменилось после открытия; запись отменена',
    'Cold Steel III installation not found':'Установка Cold Steel III не найдена',
    'Game directory not found':'Папка игры не найдена',
    'No readable item tables found':'Не найдено доступных для чтения таблиц предметов',
    'Select an original English catalog. This file contains Russian or another language.':'Выберите оригинальный английский каталог. Этот файл содержит русский или другой язык.',
}
EXACT={
    'ID 249 нельзя добавлять в обычный инвентарь; существующую запись можно удалить количеством 0':'ID 249 cannot be added to the regular inventory; set quantity to 0 to remove an existing entry',
    'Неизвестная версия или тип файла сохранения':'Unknown save version or file type',
    'Длина в заголовке не совпадает с длиной файла':'The header length does not match the file length',
    'Таблица предметов выходит за конец сохранения':'The inventory table extends past the end of the save',
    'Обнаружены предметы после пустых слотов — неизвестная структура инвентаря':'Items were found after empty slots; unsupported inventory structure',
    'Не найдена достаточная область свободных слотов инвентаря':'Not enough empty inventory slots were found',
    'ID предмета должен быть числом от 0 до 65535, кроме 9999':'Item ID must be an integer from 0 to 65535, excluding 9999',
    'Количество должно быть в диапазоне 0–99':'Quantity must be an integer from 0 to 99',
    'Недостаточно свободных слотов для добавления':'Not enough free slots to add these items',
    'Повреждена строка заголовка таблицы TBL':'Invalid TBL header string',
    'Недопустимый тип записи в TBL':'Invalid TBL record type',
    'Слишком короткая таблица TBL':'The TBL file is too short',
    'Это не таблица предметов Cold Steel III':'This is not a Cold Steel III item table',
    'Повреждена таблица типов':'The TBL type table is damaged',
    'Повторяющийся тип записи в заголовке TBL':'Duplicate record type in the TBL header',
    'Количество записей в заголовке TBL не совпадает':'The TBL header record count does not match',
    'Файл обрывается перед записью TBL':'The file ends before a TBL record',
    'Некорректная длина записи TBL':'Invalid TBL record length',
    'TBL содержит неожиданное количество данных':'Unexpected data length in the TBL file',
    'Названия предметов не найдены':'No item names were found',
    'Файл изменился во время чтения; повторите открытие':'The file changed while being read; open it again',
    'Таблица слишком большая':'The item table is too large',
    'Каталог слишком большой':'The catalog is too large',
    'Неверный формат JSON-каталога':'Invalid JSON catalog format',
    'Неверная запись JSON-каталога':'Invalid JSON catalog record',
    'Некорректный ID в JSON-каталоге':'Invalid item ID in the JSON catalog',
    'Пустое название в JSON-каталоге':'Invalid or empty item name in the JSON catalog',
    'Неверное описание в JSON-каталоге':'Invalid description in the JSON catalog',
    'Неверные характеристики в JSON-каталоге':'Invalid stats in the JSON catalog',
    'Неизвестная категория в JSON-каталоге':'Unknown category in the JSON catalog',
    'CSV должен быть в кодировке UTF-8':'The CSV must use UTF-8 encoding',
    'Не найдены строки CSV вида ID,Название[,Описание]':'No CSV rows in ID,Name[,Description] format were found',
    'Поддерживаются только .tbl и .csv':'Only .tbl and .csv files are supported',
    'Выбранная папка не содержит таблиц предметов Cold Steel III. Нужна папка с каталогом data (корневая папка игры).':'The selected folder does not contain Cold Steel III item tables. Select the game root folder containing data.',
    'Таблицы обнаружены, но прочитать ни одну не удалось:':'Item tables were found, but none could be read:',
}
PATTERNS=[
 (r'Размер (\d+) байт вместо ожидаемых (\d+)\. Редактор поддерживает проверенный тип сохранений CS3 NISA для Windows\.',r'File size: \1 bytes; expected \2. Only the verified CS3 NISA Windows save format is supported.'),
 (r'Неизвестные данные в записи инвентаря №(\d+); запись отменена',r'Unknown inventory data in slot \1; write cancelled'),
 (r'Слот №(\d+) помечен пустым, но содержит количество (\d+)',r'Slot \1 is marked empty but has quantity \2'),
 (r'Недопустимое количество (\d+) для ID (\d+), слот (\d+)',r'Invalid quantity \1 for ID \2 in slot \3'),
 (r'Дублирующийся ID (\d+) — редактор остановлен',r'Duplicate item ID \1; operation stopped'),
 (r'Неверный UTF-8 для предмета ID (\d+)',r'Invalid UTF-8 for item ID \1'),
 (r'Конфликтующие названия для ID (\d+)',r'Conflicting item names for ID \1'),
 (r'Повторяющийся ID (\d+) в JSON-каталоге',r'Duplicate item ID \1 in the JSON catalog'),
 (r'Повреждённые флаги TBL, ID (\d+)',r'Invalid TBL flags for item ID \1'),
 (r'Неполная запись TBL, ID (\d+)',r'Incomplete TBL record for item ID \1'),
 (r'Незавершённые строки TBL, ID (\d+)',r'Unterminated TBL strings for item ID \1'),
 (r'Это не t_item\*\.tbl: найдена таблица (\w+)',r'Not a t_item*.tbl file: found table \1'),
 (r'Неизвестный тип записи: (\w+)',r'Unknown record type: \1'),
]


def error_text(error,language):
    value=str(error)
    if language=='ru':
        for en,ru in PAIRS.items():value=value.replace(en,ru)
        value=value.replace('No compatible saveXXX.dat found.','Совместимые saveXXX.dat не найдены.')
        return value
    for ru,en in sorted(EXACT.items(),key=lambda pair:-len(pair[0])):value=value.replace(ru,en)
    for pattern,replacement in PATTERNS:value=re.sub(pattern,replacement,value)
    value=value.replace('несовместимый размер или файл обновляется','unsupported size or the file is being updated')
    value=value.replace('файл изменился во время чтения','the file changed while being read')
    value=value.replace('Не удалось открыть папку','Could not open folder')
    return value
