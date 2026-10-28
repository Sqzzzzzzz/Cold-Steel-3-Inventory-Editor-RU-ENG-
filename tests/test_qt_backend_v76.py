"""Controller-only regression tests for the experimental Qt shell.
They run without Qt, a game installation, or any proprietary game assets.
"""
from __future__ import annotations
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from cs3_save import TABLE_OFFSET, TABLE_END, CS3Save
from qt_backend import EditorCore
from test_v70_release_regressions import synthetic_save

ROOT=Path(__file__).resolve().parents[1]

class QtBackendSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.prev=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.tmp.name
        self.core=EditorCore()
        self.path=Path(self.tmp.name)/'save016.dat'
        self.original=synthetic_save(((20,2),(60,8),(3200,1)))
        self.path.write_bytes(self.original)
        self.core.open_file(self.path)

    def tearDown(self):
        if self.prev is None:os.environ.pop('APPDATA',None)
        else:os.environ['APPDATA']=self.prev
        self.tmp.cleanup()

    def test_batch_edit_undo_leaves_noninventory_bytes(self):
        self.core.change({20:77,60:0,100:3,3200:5})
        result=self.core.save.bytes()
        self.assertEqual(CS3Save(result).get_quantity(100),3)
        self.assertEqual(result[:TABLE_OFFSET],self.original[:TABLE_OFFSET])
        self.assertEqual(result[TABLE_END:],self.original[TABLE_END:])
        self.assertTrue(self.core.undo())
        self.assertEqual(self.core.save.bytes(),self.original)

    def test_reject_malformed_batch_without_history(self):
        before=self.core.save.bytes()
        with self.assertRaises(ValueError):self.core.change({20:4,9999:1})
        self.assertEqual(self.core.save.bytes(),before)
        self.assertFalse(self.core.undo_stack)

    def test_save_copy_does_not_change_original_or_reset_dirty(self):
        self.core.change({20:9})
        target=Path(self.tmp.name)/'save016_edited.dat'
        self.core.save_copy(target)
        self.assertEqual(self.path.read_bytes(),self.original)
        self.assertTrue(self.core.save.changed)
        self.assertEqual(CS3Save.from_file(target).get_quantity(20),9)
        with self.assertRaises(FileExistsError):self.core.save_copy(target)
        with self.assertRaises(ValueError):self.core.save_copy(self.path)

    def test_overwrite_creates_backup_and_can_reopen(self):
        self.core.change({20:99})
        backup=self.core.overwrite_with_backup()
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_bytes(),self.original)
        self.assertEqual(CS3Save.from_file(self.path).get_quantity(20),99)
        self.assertFalse(self.core.save.changed)
        self.assertEqual(self.core.source,self.path)
        self.assertIsNone(self.core.overwrite_with_backup())

    def test_external_modification_blocks_overwrite(self):
        self.core.change({60:2})
        self.path.write_bytes(synthetic_save(((20,12),(60,8),(3200,1))))
        with self.assertRaises(RuntimeError):self.core.overwrite_with_backup()
        self.assertEqual(CS3Save.from_file(self.path).get_quantity(20),12)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))),0)

    def test_settings_and_favorites_separate_from_stable(self):
        self.core.toggle_favorite(60)
        self.core.set_language('en')
        fresh=EditorCore()
        self.assertIn(60,fresh.favorites)
        self.assertEqual(fresh.language,'en')
        self.assertFalse((Path(self.tmp.name)/'CS3InventoryEditor'/'settings.json').exists())

    def test_english_rescan_does_not_erase_existing_russian_name(self):
        self.core.base={60:{'id':60,'name':'Русское имя','description':'Русское описание','category':'material'}}
        new=SimpleNamespace(root=Path(self.tmp.name),files=[self.path],
             items={60:{'id':60,'name':'U-Material','description':'English description','category':'material'}},errors=[])
        self.core.apply_scan_result(new)
        self.assertEqual(self.core.catalog[60]['name'],'Русское имя')
        self.assertEqual(self.core.catalog[60]['description'],'Русское описание')
        self.assertEqual(self.core.english[60]['name'],'U-Material')

    def test_scan_stays_in_beta_and_retains_overrides(self):
        self.core.overrides={60:{'id':60,'name':'Точный перевод','description':'Да','_locale':'ru'}}
        mock=SimpleNamespace(root=Path(self.tmp.name),files=[self.path],
            items={60:{'id':60,'name':'U-Material','description':'Material','category':'material','_source':'base'},
                   90:{'id':90,'name':'Orb','description':'An Orb','category':'material','_source':'dlc'}},errors=[])
        self.core.apply_scan_result(mock)
        self.assertEqual(self.core.catalog[60]['name'],'Точный перевод')
        self.assertEqual(self.core.english[90]['name'],'Orb')
        self.assertTrue((Path(self.tmp.name)/'CS3InventoryEditor_BETA'/'catalog_scanned.json').exists())

class QtSourceSmoke(unittest.TestCase):
    def test_qt_source_parses_without_qt_import(self):
        source=(ROOT/'qt_window.py').read_text('utf-8')
        tree=ast.parse(source)
        self.assertTrue(any(isinstance(n,ast.ClassDef) and n.name=='MainWindow' for n in tree.body))
        for name in ('show_section','update_tables','apply_bulk','load_latest',
                     'overwrite_dialog','switch_language','scan_game','retranslate'):
            self.assertIn(f'def {name}(',source)
        self.assertIn('GlassPanel',source)
        self.assertIn('PySide6',source)

if __name__=='__main__': unittest.main()
