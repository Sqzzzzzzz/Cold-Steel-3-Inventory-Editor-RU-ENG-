"""Verified Cold Steel III item table reader and durable catalog helpers.

Reads the user-provided game table layout. Does not modify game .tbl files.
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import re
import sys
import struct

from categories import classify_record, CATEGORY_TO_GROUP, CATEGORY_NAMES

MAX_ID = 65535
EMPTY_ID = 9999


def resource_path(filename: str) -> Path:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return root / filename


def user_catalog_path() -> Path:
    appdir = os.environ.get('APPDATA')
    root = Path(appdir) if appdir else Path.home() / '.config'
    return root / 'CS3InventoryEditor_BETA' / 'catalog_overrides.json'


def _cstring(data: bytes, p: int) -> tuple[str, int]:
    end = data.find(b'\0', p)
    if end < 0 or end - p > 64 or end == p:
        raise ValueError('Повреждена строка заголовка таблицы TBL')
    try:
        return data[p:end].decode('ascii'), end + 1
    except UnicodeDecodeError as exc:
        raise ValueError('Недопустимый тип записи в TBL') from exc


def parse_item_tbl(source: str | Path | bytes) -> dict[int, dict]:
    """Extract ID, translated name, description and record family.

    Header: u16 record count, u32 group count, groups of name\0 + u32 count.
    Record: type\0 + u16 body size + body; body begins with u16 item ID.
    Both record families contain the same ItemData prefix: the name begins
    127 bytes after the flag C-string. The two bytes immediately before the
    name need not be FF FF. ItemQData has six additional arts after ItemData.
    Zero-count groups (typically item_q in DLC tables) are valid.
    """
    if isinstance(source,bytes):data=source
    else:
        path=Path(source)
        if path.stat().st_size>16*1024*1024:raise ValueError('Таблица слишком большая')
        with path.open('rb') as stream:data=stream.read(16*1024*1024+1)
    if len(data)>16*1024*1024:raise ValueError('Таблица слишком большая')
    if len(data) < 32:
        raise ValueError('Слишком короткая таблица TBL')
    count = int.from_bytes(data[:2], 'little')
    groups = int.from_bytes(data[2:6], 'little')
    if not 1 <= count <= 65000 or not 1 <= groups <= 16:
        raise ValueError('Это не таблица предметов Cold Steel III')
    pos = 6
    header_groups = {}
    for _ in range(groups):
        typ, pos = _cstring(data, pos)
        if pos + 4 > len(data):
            raise ValueError('Повреждена таблица типов')
        n = int.from_bytes(data[pos:pos+4], 'little')
        pos += 4
        if typ not in ('item', 'item_q'):
            raise ValueError('Это не t_item*.tbl: найдена таблица '+typ)
        if typ in header_groups:
            raise ValueError('Повторяющийся тип записи в заголовке TBL')
        header_groups[typ] = n
    if sum(header_groups.values()) != count:
        raise ValueError('Количество записей в заголовке TBL не совпадает')
    result: dict[int, dict] = {}
    # Keep zero-sized groups in the tally. Most costume DLC tables declare
    # item_q: 0; comparing a sparse observed dict rejects valid DLC.
    observed: dict[str, int] = {name: 0 for name in header_groups}
    for _ in range(count):
        typ, pos = _cstring(data, pos)
        if typ not in header_groups:
            raise ValueError('Неизвестный тип записи: '+typ)
        if pos + 2 > len(data):
            raise ValueError('Файл обрывается перед записью TBL')
        sz = int.from_bytes(data[pos:pos+2], 'little')
        pos += 2
        if sz < 72 or pos + sz > len(data):
            raise ValueError('Некорректная длина записи TBL')
        payload = data[pos:pos+sz]
        pos += sz
        observed[typ] = observed.get(typ, 0) + 1
        item_id = int.from_bytes(payload[:2], 'little')
        if item_id == EMPTY_ID:
            continue
        # ItemQData contains the same ItemData prefix, followed by six arts.
        # Source: SenPatcher native/sen3/tbl.{h,cpp}. Do not search stats for
        # FF FF: that value is legal *inside* metadata and isn't a delimiter.
        flag_end = payload.find(b'\0', 4, min(len(payload), 68))
        if flag_end < 0:
            raise ValueError(f'Повреждённые флаги TBL, ID {item_id}')
        text_at = flag_end + 1 + 127
        if text_at >= len(payload):
            raise ValueError(f'Неполная запись TBL, ID {item_id}')
        metadata = payload[flag_end+1:text_at]
        type_code = int.from_bytes(metadata[:2], 'little')
        strings = payload[text_at:].split(b'\0', 2)
        if len(strings) < 3:
            raise ValueError(f'Незавершённые строки TBL, ID {item_id}')
        try:
            name = strings[0].decode('utf-8').strip()
            desc = strings[1].decode('utf-8').strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f'Неверный UTF-8 для предмета ID {item_id}') from exc
        if not name or not all(c.isprintable() for c in name):
            continue
        if item_id in result and result[item_id]['name'] != name:
            raise ValueError(f'Конфликтующие названия для ID {item_id}')
        # Element is metadata byte 4, after the variable-length flag string.
        element = ({1:'earth',2:'water',3:'fire',4:'wind',5:'time',6:'space',7:'mirage'}
                   .get(metadata[4]) if type_code & 0xff in (0xc8,0xc9) else None)
        result[item_id] = {'id': item_id, 'name': name, 'description': desc,
                           'kind': 'quartz' if typ == 'item_q' else 'item',
                           'category': classify_record(typ, type_code),
                           'type_code':type_code,
                           'character':int.from_bytes(payload[2:4],'little')}
        if element:
            result[item_id]['element'] = element
        stats=dict(zip(('STR','DEF','ATS','ADF','ACC','EVA','SPD','MOV','HP','EP'),
                       struct.unpack_from('<10h',metadata,98)))
        if any(stats.values()):result[item_id]['stats']={k:v for k,v in stats.items() if v}
        if typ == 'item_q':
            result[item_id]['effects'] = [list(values) for n in range(6)
                if (values := struct.unpack_from('<7H',metadata,14+n*14))[0]]
            if len(strings[2]) == 20:
                result[item_id]['arts'] = list(dict.fromkeys(
                    art for art in struct.unpack_from('<6H',strings[2],8) if art not in (0,65535)))
            # All 307 supplied quartz agree with this native float (0/1/2).
            # Preserve unknown values instead of guessing a tier from a name.
            tier=struct.unpack_from('<f',metadata,11)[0]
            if tier in (0.0,1.0,2.0):
                result[item_id]['rarity']={0.0:'normal',1.0:'r',2.0:'sr'}[tier]
    if observed != header_groups or pos != len(data):
        raise ValueError('TBL содержит неожиданное количество данных')
    if not result:
        raise ValueError('Названия предметов не найдены')
    if not isinstance(source,bytes):
        from quartz_details import enrich_english_descriptions
        enrich_english_descriptions(result,path.parent)
    return result


def parse_csv(source: str | Path) -> dict[int, dict]:
    try:
        content = Path(source).read_text(encoding='utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('CSV должен быть в кодировке UTF-8') from exc
    delimiter = ';' if content.count(';') > content.count(',') * 2 else ','
    output = {}
    for row in csv.reader(io.StringIO(content), delimiter=delimiter):
        if len(row) < 2:
            continue
        try:
            item_id = int(row[0].strip())
        except ValueError:
            continue
        if item_id < 0 or item_id > MAX_ID or item_id == EMPTY_ID:
            continue
        name = row[1].strip()
        if name:
            category = row[2].strip().casefold() if len(row) >= 4 else ''
            localized_category = {v.casefold(): k for k, v in CATEGORY_NAMES.items()}.get(category)
            category = localized_category or category
            has_category = category in ('кварц', 'предмет', 'quartz', 'item') or category in CATEGORY_TO_GROUP
            desc_index = 3 if has_category else 2
            entry = {'id': item_id, 'name': name,
                     'description': row[desc_index].strip() if len(row) > desc_index else ''}
            if has_category:
                entry['kind'] = 'quartz' if category in ('кварц','quartz') or category == 'quartz_normal' else 'item'
                if category in CATEGORY_TO_GROUP:
                    entry['category'] = category
            output[item_id] = entry
    if not output:
        raise ValueError('Не найдены строки CSV вида ID,Название[,Описание]')
    return output


def load_external_catalog(path: str | Path) -> dict[int, dict]:
    suffix = Path(path).suffix.lower()
    if suffix == '.tbl':
        return parse_item_tbl(path)
    if suffix == '.csv':
        return parse_csv(path)
    raise ValueError('Поддерживаются только .tbl и .csv')


def load_catalog_json(path: str | Path) -> dict[int, dict]:
    path=Path(path)
    if path.stat().st_size > 16*1024*1024:
        raise ValueError('Каталог слишком большой')
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    rows = raw.get('items') if isinstance(raw, dict) else raw
    result = {}
    if not isinstance(rows, list):
        raise ValueError('Неверный формат JSON-каталога')
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('Неверная запись JSON-каталога')
        item_id = row.get('id')
        if type(item_id) is not int or not 0 <= item_id <= MAX_ID or item_id == EMPTY_ID:
            raise ValueError('Некорректный ID в JSON-каталоге')
        name = row.get('name')
        if not isinstance(name, str) or not name.strip() or len(name)>4096:
            raise ValueError('Пустое название в JSON-каталоге')
        if not isinstance(row.get('description',''),str):
            raise ValueError('Неверное описание в JSON-каталоге')
        if ('generated_description' in row and
                (not isinstance(row['generated_description'],str) or len(row['generated_description'])>16384
                 or row.get('generated_description_locale') not in ('en','ru','fr'))):
            raise ValueError('Неверное описание в JSON-каталоге')
        if 'arts' in row and (not isinstance(row['arts'],list) or len(row['arts'])>6 or
                any(type(v) is not int or not 0<=v<=65535 for v in row['arts'])):
            raise ValueError('Неверное описание в JSON-каталоге')
        if 'effects' in row and (not isinstance(row['effects'],list) or len(row['effects'])>6 or
                any(not isinstance(v,list) or len(v)!=7 or
                    any(type(n) is not int or not 0<=n<=65535 for n in v) for v in row['effects'])):
            raise ValueError('Неверное описание в JSON-каталоге')
        if 'category' in row and (not isinstance(row['category'],str) or row['category'] not in CATEGORY_TO_GROUP):
            raise ValueError('Неизвестная категория в JSON-каталоге')
        stats=row.get('stats',{})
        if not isinstance(stats,dict) or any(k not in ('STR','DEF','ATS','ADF','ACC','EVA','SPD','MOV','HP','EP') or
                type(v) is not int or not -32768<=v<=32767 for k,v in stats.items()):
            raise ValueError('Неверные характеристики в JSON-каталоге')
        if item_id in result:
            raise ValueError(f'Повторяющийся ID {item_id} в JSON-каталоге')
        result[item_id] = row
    return result


def save_catalog_json(path: str | Path, catalog: dict[int, dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps({'items': [catalog[k] for k in sorted(catalog)]},
                            ensure_ascii=False, indent=1)
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='catalog_', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(serialized)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def clear_codes(value: str) -> str:
    """Strip small number/color-format codes from in-game help text."""
    return re.sub(r'#[0-9]+[A-Za-z]', '', value)
