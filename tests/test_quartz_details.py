"""Native help recovery, using synthetic tables without bundled game data."""
import struct
from types import SimpleNamespace

import pytest

from catalog_core import load_catalog_json, parse_item_tbl, save_catalog_json
from game_scan import scan_game_tables
from qt_backend import EditorCore
from quartz_details import enrich_english_descriptions, generated_help, read_magic_help


def table(rows):
    counts = {}
    for kind, _ in rows:
        counts[kind] = counts.get(kind, 0) + 1
    header = struct.pack('<HI', len(rows), len(counts))
    header += b''.join(k.encode()+b'\0'+struct.pack('<I', n) for k, n in counts.items())
    return header + b''.join(k.encode()+b'\0'+struct.pack('<H', len(b))+b for k, b in rows)


def quartz(iid, name, effects=(), arts=(), description='◆', stat=0):
    metadata = bytearray(127)
    metadata[0] = 200
    metadata[4] = 1
    for n, effect in enumerate(effects):
        struct.pack_into('<7H', metadata, 14+14*n, *effect)
    struct.pack_into('<h', metadata, 100, stat)
    body = struct.pack('<HH', iid, 65535)+b'SLZ\0'+metadata
    body += name.encode()+b'\0'+description.encode()+b'\0'+bytes(8)
    body += struct.pack('<6H', *(list(arts)+[65535]*(6-len(arts))))
    return 'item_q', body


def help_row(iid, text, arguments=1):
    return 'ItemHelpData', struct.pack('<H', iid)+text.encode()+b'\0'+struct.pack('<H', arguments)+bytes(7)


def magic_row(iid, name, description):
    return 'magic', struct.pack('<HH', iid, 0)+b'0\0'+bytes(102)+b'animation\0'+name.encode()+b'\0'+description.encode()+b'\0'


def native_files(folder):
    folder.mkdir(parents=True, exist_ok=True)
    effects = lambda eid, value: (eid, value, 0, 0, 0, 0, 0)
    rows = [quartz(3300, 'Needle Shoot', arts=(20, 20, 0)),
            quartz(3396, 'Waterfall', (effects(320, 0), effects(244, 50))),
            quartz(3487, 'Revolution', (effects(320, 0), effects(243, 50)))]
    rows += [quartz(i, f'Strike {n}', (effects(206, n*3),))
             for n, i in enumerate((3409, 3422, 3438), 1)]
    item = folder/'t_item_en.tbl'
    item.write_bytes(table(rows))
    (folder/'t_itemhelp.tbl').write_bytes(table([
        help_row(0, 'English help', 0),
        help_row(206, 'Critical rate+%d%%'),
        help_row(243, 'Deal bonus damage to high-level enemies (max+%d%%).'),
        help_row(244, 'Deal bonus damage to low-level enemies (max+%d%%).')]))
    (folder/'t_magic.tbl').write_bytes(table([
        magic_row(20, 'Needle Shoot', 'Launches a sharply pointed boulder at an enemy.'),
        magic_row(21, 'English art', 'Strikes the enemy.')] ))
    return item


def test_six_quartz_recover_native_help_without_replacing_original_text(tmp_path):
    item = native_files(tmp_path)
    raw = parse_item_tbl(item.read_bytes())
    assert raw[3300]['arts'] == [20]
    assert raw[3438]['effects'] == [[206, 9, 0, 0, 0, 0, 0]]
    assert all('generated_description' not in r for r in raw.values())
    rows = parse_item_tbl(item)
    assert all(r['description'] == '◆' for r in rows.values())
    assert rows[3300]['generated_description'] == 'Needle Shoot\nLaunches a sharply pointed boulder at an enemy.'
    assert rows[3396]['generated_description'] == 'Deal bonus damage to low-level enemies (max+50%).'
    assert rows[3487]['generated_description'] == 'Deal bonus damage to high-level enemies (max+50%).'
    for n, iid in enumerate((3409, 3422, 3438), 1):
        assert rows[iid]['generated_description'] == f'Critical rate+{n*3}%'
        assert rows[iid]['generated_description_sources'] == ['t_itemhelp.tbl#206']


def test_ambiguous_magic_ids_are_excluded_without_disabling_unique_arts(tmp_path):
    item = native_files(tmp_path)
    magic = tmp_path/'t_magic.tbl'
    magic.write_bytes(table([
        magic_row(20, 'Needle Shoot', 'Strikes the enemy.'),
        magic_row(2500, 'Link attack', 'First English description.'),
        magic_row(2500, 'Link attack', 'Another English description.'),
        magic_row(2500, 'Link attack', 'First English description.')]))
    rows = read_magic_help(magic)
    assert 2500 not in rows
    assert rows[20]['name'] == 'Needle Shoot'
    assert parse_item_tbl(item)[3300]['generated_description'] == 'Needle Shoot\nStrikes the enemy.'


@pytest.mark.parametrize('provider', ('t_magic.tbl', 't_itemhelp.tbl'))
@pytest.mark.parametrize('bad_data', (None, b'truncated', b'\xff'*32))
def test_missing_or_malformed_optional_file_does_not_break_import(tmp_path, provider, bad_data):
    item = native_files(tmp_path)
    path = tmp_path/provider
    if bad_data is None:
        path.unlink()
    else:
        path.write_bytes(bad_data)
    rows = parse_item_tbl(item)
    assert len(rows) == 6
    missing, retained = (3300, 3438) if provider == 't_magic.tbl' else (3438, 3300)
    assert 'generated_description' not in rows[missing]
    assert rows[retained]['generated_description']


def test_russian_help_cannot_leak_into_english_catalog(tmp_path):
    item = native_files(tmp_path)
    (tmp_path/'t_itemhelp.tbl').write_bytes(table([help_row(206, 'Критический удар+%d%%')]))
    rows = parse_item_tbl(item)
    assert 'generated_description' not in rows[3438]
    assert rows[3300]['generated_description']


def test_real_descriptions_stats_and_unknown_effects_are_preserved(tmp_path):
    item = native_files(tmp_path)
    rows = parse_item_tbl(item.read_bytes())
    rows[3409]['description'] = 'The original description.'
    rows[3422]['stats'] = {'DEF': 40}
    rows[3438]['effects'][0][2] = 2  # unverified additional parameter
    rows[3396]['effects'] = [[999, 50, 0, 0, 0, 0, 0]]
    enrich_english_descriptions(rows, tmp_path)
    for iid in (3409, 3422, 3438, 3396):
        assert 'generated_description' not in rows[iid]
    assert rows[3409]['description'] == 'The original description.'
    assert rows[3422]['stats'] == {'DEF': 40}


def test_import_cache_and_runtime_language_keep_generated_help(tmp_path, monkeypatch):
    item = native_files(tmp_path/'tables')
    monkeypatch.setenv('APPDATA', str(tmp_path/'settings'))
    core = EditorCore()
    core.base = {3438: {'id':3438, 'name':'Удар 3', 'description':'◆', 'kind':'quartz', 'category':'quartz_normal'}}
    core.rebuild_catalog()
    core.import_english_catalog(item)
    core.set_language('en')
    assert core.details_text(3438) == 'Critical rate+9%'
    restarted = EditorCore()
    restarted.set_language('en')
    assert restarted.details_text(3438) == 'Critical rate+9%'
    core.set_language('ru')
    assert 'Critical' not in core.details_text(3438)
    core.english[3438]['description'] = 'The original description.'
    core.set_language('en')
    assert core.details_text(3438) == 'The original description.'


def test_game_scanner_and_json_export_keep_native_help(tmp_path):
    item = native_files(tmp_path/'game/data/text/dat_en')
    result = scan_game_tables(tmp_path/'game')
    assert not result.errors
    assert result.items[3438]['generated_description'] == 'Critical rate+9%'
    target = tmp_path/'export.json'
    save_catalog_json(target, result.items)
    assert load_catalog_json(target)[3300] == result.items[3300]
    assert item.exists()


@pytest.mark.parametrize('fields', (
    {'generated_description': [], 'generated_description_locale':'en'},
    {'generated_description':'text', 'generated_description_locale':'invalid'},
    {'arts':[True]}, {'effects':[[206, 9]]}, {'effects':[[206, 9, 0, 0, 0, 0, 65536]]}))
def test_invalid_cached_help_is_rejected(tmp_path, fields):
    target = tmp_path/'bad.json'
    save_catalog_json(target, {3300: {'id':3300, 'name':'Needle Shoot', **fields}})
    with pytest.raises(ValueError):
        load_catalog_json(target)


def test_legacy_description_accessor_uses_same_language_guard():
    from app import Editor
    record = {'description':'◆', 'generated_description':'Critical rate+9%', 'generated_description_locale':'en'}
    legacy = SimpleNamespace(language='en', english_catalog={3438:record})
    assert Editor._get_description(legacy, 3438) == 'Critical rate+9%'
    assert generated_help(record, 'ru') == ''
