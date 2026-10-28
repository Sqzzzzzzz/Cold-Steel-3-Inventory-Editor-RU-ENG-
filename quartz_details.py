"""Recover missing English quartz help from the owner's native game tables.

Primary descriptions remain untouched. Only documented record layouts and the
three parameterised effect IDs verified against the supplied tables are used.
No game data is downloaded or bundled by this module.
"""
from pathlib import Path
import struct

from catalog_locale import catalog_locale

_MAX_TABLE_BYTES = 16 * 1024 * 1024
_KNOWN_EFFECT_IDS = frozenset((206, 243, 244))


def _string(data, offset, encoding='utf-8', limit=65535):
    end = data.find(b'\0', offset)
    if end < offset or end-offset > limit:
        raise ValueError('Invalid native text string')
    return data[offset:end].decode(encoding), end+1


def _entries(path, allowed, required):
    path = Path(path)
    if path.stat().st_size > _MAX_TABLE_BYTES:
        raise ValueError('Native text table is too large')
    with path.open('rb') as stream:
        data = stream.read(_MAX_TABLE_BYTES+1)
    if not 6 <= len(data) <= _MAX_TABLE_BYTES:
        raise ValueError('Invalid native text table size')
    count, groups = struct.unpack_from('<HI', data)
    if not 0 < count <= 65000 or not 0 < groups <= 16:
        raise ValueError('Invalid native text table header')
    pos = 6
    declared = {}
    for _ in range(groups):
        kind, pos = _string(data, pos, 'ascii', 64)
        if kind not in allowed or kind in declared or pos+4 > len(data):
            raise ValueError('Unsupported native text table')
        declared[kind] = struct.unpack_from('<I', data, pos)[0]
        pos += 4
    if required not in declared or sum(declared.values()) != count:
        raise ValueError('Native text record count does not match')
    observed = dict.fromkeys(declared, 0)
    rows = []
    for _ in range(count):
        kind, pos = _string(data, pos, 'ascii', 64)
        if kind not in observed or pos+2 > len(data):
            raise ValueError('Invalid native text record header')
        size = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        if size < 2 or pos+size > len(data):
            raise ValueError('Invalid native text record size')
        rows.append((kind, data[pos:pos+size]))
        observed[kind] += 1
        pos += size
    if observed != declared or pos != len(data):
        raise ValueError('Unexpected native text table data')
    return rows


def read_item_help(path):
    result = {}
    for kind, body in _entries(path, {'ItemHelpData', 'CompHelpData'}, 'ItemHelpData'):
        if kind != 'ItemHelpData':
            continue
        iid = struct.unpack_from('<H', body)[0]
        text, end = _string(body, 2)
        # SenPatcher ItemHelpData: ID, text, u16, seven metadata bytes.
        if end+9 != len(body) or iid in result:
            raise ValueError('Invalid or duplicate ItemHelpData')
        result[iid] = {'name': text, 'arguments': struct.unpack_from('<H', body, end)[0]}
    if catalog_locale(result) != 'en':
        raise ValueError('The item help table is not English')
    return result


def read_magic_help(path):
    result = {}
    ambiguous = set()
    for kind, body in _entries(path, {'magic', 'magicbo', 'btcalc'}, 'magic'):
        if kind != 'magic':
            continue
        iid = struct.unpack_from('<H', body)[0]
        _, pos = _string(body, 4, limit=64)
        # MagicData: 22 bytes, five (u16 + 3*u32) effects, ten bytes.
        pos += 102
        _, pos = _string(body, pos)  # animation
        name, pos = _string(body, pos)
        description, pos = _string(body, pos)
        record = {'name': name, 'description': description}
        if pos != len(body):
            raise ValueError('Invalid MagicData')
        # Stock link attacks reuse IDs with different text. They are not
        # quartz arts: exclude ambiguous IDs rather than choosing one version.
        if iid in ambiguous:
            continue
        if iid in result and result[iid] != record:
            result.pop(iid); ambiguous.add(iid); continue
        result[iid] = record
    if catalog_locale(result) != 'en':
        raise ValueError('The magic table is not English')
    return result


def _placeholder(item):
    return str(item.get('description', '')).strip() in ('', '◆', '◇')


def generated_help(item, language):
    text = item.get('generated_description')
    if (_placeholder(item) and item.get('generated_description_locale') == language
            and isinstance(text, str)):
        return text
    return ''


def enrich_english_descriptions(catalog, folder):
    """Optional sibling tables improve help without making item import fragile."""
    if catalog_locale(catalog) != 'en':
        return
    folder = Path(folder)
    try:
        help_rows = read_item_help(folder/'t_itemhelp.tbl')
    except (OSError, ValueError, UnicodeError, struct.error):
        help_rows = {}
    try:
        magic_rows = read_magic_help(folder/'t_magic.tbl')
    except (OSError, ValueError, UnicodeError, struct.error):
        magic_rows = {}
    for item in catalog.values():
        if item.get('kind') != 'quartz' or not _placeholder(item) or item.get('stats'):
            continue
        lines = []
        sources = []
        for effect in item.get('effects', []):
            effect_id, value, *unused = effect
            template = help_rows.get(effect_id)
            if effect_id not in _KNOWN_EFFECT_IDS or not template or any(unused):
                continue
            text = template['name']
            # These verified effects have one unsigned integer and optional %%.
            if template['arguments'] != 1 or text.count('%d') != 1:
                continue
            try:
                text = text % value
            except (ValueError, TypeError, OverflowError):
                continue
            if text not in lines:
                lines.append(text); sources.append(f't_itemhelp.tbl#{effect_id}')
        for art_id in item.get('arts', []):
            art = magic_rows.get(art_id)
            if art and art['description'].strip() not in ('', '◆', '◇'):
                text = art['name']+'\n'+art['description']
                if text not in lines:
                    lines.append(text); sources.append(f't_magic.tbl#{art_id}')
        if lines:
            item['generated_description'] = '\n\n'.join(lines)
            item['generated_description_locale'] = 'en'
            item['generated_description_sources'] = sources
