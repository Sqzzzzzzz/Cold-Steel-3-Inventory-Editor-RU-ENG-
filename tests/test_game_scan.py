"""Tests for Steam discovery, DLC merging, cache and UI configuration."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_scan import (candidate_table_paths, find_game_install, is_game_root,
    load_settings, save_settings, scan_game_tables, steam_library_paths)
from catalog_core import load_catalog_json, save_catalog_json


def make_tbl(item_id: int, name: str) -> bytes:
    return make_realistic_cs3_dlc(item_id, name)


def make_realistic_cs3_dlc(item_id: int, name: str, flag: str = '0') -> bytes:
    """Same CS3 item payload layout as publicly documented costume DLC maker.

    The table declares an empty item_q group and uses trailing metadata 00 00
    instead of the FF FF marker present in many base-game entries.
    """
    payload = struct.pack('<HH', item_id, 0xffff) + flag.encode('ascii') + b'\0'
    payload += struct.pack('<H4HB', 193, 0, 0, 0, 0, 0)
    payload += struct.pack('<B55H', *([0]*56))
    payload += struct.pack('<BHH', 99, 3000, 0)
    payload += name.encode('utf-8') + b'\0'
    payload += 'Описание DLC'.encode('utf-8') + b'\0' + struct.pack('<II',0,0)
    assert payload.find(b'\xff\xff', 70) == -1
    header = (struct.pack('<HI',1,2) + b'item\0' + struct.pack('<I', 1) +
              b'item_q\0' + struct.pack('<I',0))
    return header + b'item\0' + struct.pack('<H',len(payload)) + payload


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'installed game'
        self.base = self.game / 'data' / 'text' / 'dat_en' / 't_item_en.tbl'
        self.base.parent.mkdir(parents=True)
        self.base.write_bytes(make_tbl(5, 'Главный предмет'))

    def add_dlc(self, pack: str, item_id: int, name: str):
        p = self.game / 'data' / 'dlc' / 'text' / pack / 'dat_en' / 't_item.tbl'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(make_tbl(item_id, name))
        return p

    def test_scan_base_and_dlc(self):
        extra = self.add_dlc('0025', 3804, 'DLC костюм')
        result = scan_game_tables(self.game)
        self.assertTrue(is_game_root(self.game))
        self.assertEqual(len(result.files), 2)
        self.assertEqual(result.base_count, 1)
        self.assertEqual(result.added_by_dlc, 1)
        self.assertEqual(result.items[3804]['name'], 'DLC костюм')
        self.assertEqual(result.items[5]['name'], 'Главный предмет')
        self.assertEqual(candidate_table_paths(self.game), ([self.base], [extra]))

    def test_realistic_dlc_zero_quartz_group_and_no_ff_marker(self):
        """Regression for official-style DLC read failure in v4.0."""
        a = self.add_dlc('0007', 3951, 'Костюм из DLC')
        a.write_bytes(make_realistic_cs3_dlc(3951,'Костюм из DLC'))
        b = self.add_dlc('0010', 3952, 'Ещё костюм DLC')
        b.write_bytes(make_realistic_cs3_dlc(3952,'Ещё костюм DLC',flag='S1'))
        c = self.add_dlc('0011', 3953, 'DLC 0011')
        c.write_bytes(make_realistic_cs3_dlc(3953,'DLC 0011'))
        result = scan_game_tables(self.game)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.files), 4)
        self.assertEqual(result.added_by_dlc, 3)
        self.assertEqual(result.items[3951]['name'], 'Костюм из DLC')
        self.assertEqual(result.items[3952]['description'], 'Описание DLC')
        self.assertEqual(result.items[3953]['name'], 'DLC 0011')

    def test_source_precedence_and_collision_report(self):
        self.add_dlc('0025', 5, 'Другой предмет')
        result = scan_game_tables(self.game)
        self.assertEqual(result.items[5]['name'], 'Главный предмет')
        self.assertEqual(result.added_by_dlc, 0)
        self.assertEqual(len(result.conflicts), 1)

    def test_bad_dlc_and_good_dlc_partial_success(self):
        bad = self.add_dlc('0001', 99, 'Не будет загружен')
        bad.write_bytes(b'garbage')
        self.add_dlc('0002', 98, 'Рабочий')
        result = scan_game_tables(self.game)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.items[98]['name'], 'Рабочий')

    def test_only_one_localized_table_per_folder(self):
        p = self.base.parent / 't_item.tbl'
        p.write_bytes(make_tbl(333, 'Непредпочтительный язык'))
        b, d = candidate_table_paths(self.game)
        self.assertEqual(b, [self.base])
        self.assertEqual(d, [])

    def test_find_steam_game_in_other_library(self):
        steam = self.root / 'Steam'
        apps = steam / 'steamapps'
        apps.mkdir(parents=True)
        steamlib = self.root / 'Games'
        # Steam uses double backslash on Windows. Paths here use POSIX test paths.
        (apps / 'libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n"0" { "path" "' + str(steam) + '" }\n'
            '"1" { "path" "' + str(steamlib) + '" }\n}', encoding='utf-8')
        target = steamlib / 'steamapps' / 'common' / 'Game from manifest'
        (target / 'data' / 'text' / 'dat_en').mkdir(parents=True)
        (target / 'data' / 'text' / 'dat_en' / 't_item.tbl').write_bytes(make_tbl(1,'Potion'))
        (steamlib / 'steamapps' / 'appmanifest_991270.acf').write_text(
            '"AppState" { "appid" "991270" "installdir" "Game from manifest" }', encoding='utf-8')
        self.assertIn(steamlib, steam_library_paths(steam))
        self.assertEqual(find_game_install(steam_roots=[steam]), target.resolve())

    def test_prefer_selected_folder(self):
        self.assertEqual(find_game_install(self.game, steam_roots=[]), self.game.resolve())

    def test_no_game_fails_cleanly(self):
        with self.assertRaises(ValueError):
            scan_game_tables(self.root)

    def test_settings_roundtrip_fallback_and_catalog(self):
        settings_file = self.root / 'settings.json'
        config = {'theme': 'light', 'game_root': str(self.game),
                  'save_directory': str(self.root), 'auto_latest': False, 'language': 'en'}
        save_settings(config, settings_file)
        self.assertEqual(load_settings(settings_file), config)
        settings_file.write_text('{bad}', encoding='utf-8')
        self.assertEqual(load_settings(settings_file)['theme'], 'dark')
        catalog_file = self.root / 'catalog.json'
        result = scan_game_tables(self.game)
        save_catalog_json(catalog_file, result.items)
        self.assertEqual(load_catalog_json(catalog_file), result.items)

if __name__ == '__main__': unittest.main()
