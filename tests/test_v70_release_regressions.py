"""Synthetic, game-independent safety/performance/localization regression tests."""
from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cs3_save import CS3Save, SAVE_SIZE, TABLE_OFFSET, TABLE_END, RECORD_SIZE, RECORD_COUNT, EMPTY_ID
from i18n import EN, set_language, tr
from game_icons import EXACT_ITEM_ICON_FILES, GAME_ICON_FILES, icon_key, ALL_ORIGINAL_FILES
from catalog_core import load_catalog_json

ROOT = Path(__file__).resolve().parents[1]


def synthetic_save(items=((20, 3), (60, 9), (420, 2))):
    data = bytearray(SAVE_SIZE)
    data[:8] = bytes.fromhex('02 00 00 00 01 00 00 00')
    data[8:12] = SAVE_SIZE.to_bytes(4, 'little')
    marker = b'outside-table-safe!'
    data[150:150+len(marker)] = marker
    data[TABLE_OFFSET:TABLE_END] = ((EMPTY_ID.to_bytes(2,'little') + bytes(RECORD_SIZE - 2)) * RECORD_COUNT)
    for slot, (item_id, qty) in enumerate(items):
        pos = TABLE_OFFSET + slot * RECORD_SIZE
        data[pos:pos+4] = item_id.to_bytes(2,'little') + qty.to_bytes(2,'little')
    return bytes(data)


class BatchSafety(unittest.TestCase):
    def test_bulk_edit_is_atomic_and_respects_unmodified_bytes(self):
        original = synthetic_save()
        save = CS3Save(original)
        save.set_quantities({20: 5, 60: 0, 400: 8, 401: 99})
        self.assertEqual([(i.item_id, i.quantity) for i in save.items()],
                         [(20,5),(420,2),(400,8),(401,99)])
        self.assertEqual(save.bytes()[:TABLE_OFFSET], original[:TABLE_OFFSET])
        self.assertEqual(save.bytes()[TABLE_END:], original[TABLE_END:])
        self.assertEqual(save.bytes()[100:200], original[100:200])
        self.assertEqual(CS3Save(save.bytes()).get_quantity(401),99)

    def test_invalid_group_rolls_back_without_changing_bytes(self):
        save = CS3Save(synthetic_save())
        before = save.bytes()
        for changes in ({20:5,401:100}, {60:0, 9999:1}, {61:1, 62:-1},
                        {20:True}, {20:3.5}):
            with self.assertRaises(ValueError):
                save.set_quantities(changes)
            self.assertEqual(save.bytes(),before)
        self.assertEqual(save.get_quantity(60),9)

    def test_many_item_append_and_undo_bytes(self):
        save = CS3Save(synthetic_save())
        before = save.bytes()
        save.set_quantities({i:1 for i in range(1000,1500)})
        self.assertEqual(save.occupied_count,503)
        self.assertTrue(save.changed)
        self.assertEqual(CS3Save(save.bytes()).occupied_count,503)
        save._data=bytearray(before)  # same restoration interface used by GUI undo
        self.assertEqual(save.bytes(),before)

    def test_zero_for_absent_item_is_noop(self):
        save=CS3Save(synthetic_save())
        before=save.bytes()
        save.set_quantities({400:0})
        self.assertEqual(save.bytes(),before)

class TranslationAndArt(unittest.TestCase):
    def test_current_build_label_and_late_phrase_updates(self):
        set_language('en')
        try:
            self.assertEqual(tr('  •  ВЕРСИЯ 7.0'), '  •  VERSION 7.0')
            self.assertEqual(tr('Количество должно быть в диапазоне 1–99'),
                             'Quantity must be between 1–99')
            self.assertIn('No original English',tr('Английский каталог не загружен. Импортируйте оригинальную таблицу через «Инструменты».'))
        finally:
            set_language('ru')

    def test_exact_material_icon_and_referenced_filenames(self):
        self.assertEqual(EXACT_ITEM_ICON_FILES[60], 'U-Material (Sen III Item).png')
        self.assertIn(EXACT_ITEM_ICON_FILES[60],ALL_ORIGINAL_FILES)
        if (ROOT/'catalog_builtin.json').exists():
            cat = load_catalog_json(ROOT/'catalog_builtin.json')
            self.assertEqual(icon_key(cat[60],60),'material_u')

    def test_language_catalogs_have_unmixed_core_texts(self):
        if not (ROOT/'catalog_builtin.json').exists():
            return  # source-only package obtains user-owned game data at runtime
        import re
        ru=load_catalog_json(ROOT/'catalog_builtin.json')
        en=load_catalog_json(ROOT/'catalog_english.json')
        self.assertEqual(len(ru),1233)
        self.assertEqual(len(en),1240)
        self.assertEqual(set(ru),set(en) - set(en).difference(ru))
        self.assertFalse(any(re.search('[А-Яа-яЁё]',v['name']+v.get('description','')) for v in en.values()))
        self.assertFalse(any('Faculty Swimsuit' in v['name'] for v in ru.values()))

if __name__=='__main__': unittest.main()
