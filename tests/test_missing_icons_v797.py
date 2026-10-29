"""Missing-icon regressions: demo IDs and translated legacy catalogs."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from catalog_core import resource_path, save_catalog_json
from cs3_save import CS3Save
from game_scan import config_dir
from original_item_icons import original_icon_for_item
from preview_demo import demo_catalog, synthetic_demo_save
from qt_backend import EditorCore


class MissingIconRegressions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.environment=patch.dict(os.environ,{'APPDATA':str(self.root/'profile')})
        self.environment.start()
        self.legacy={
            1200:{'id':1200,'name':'Русский клинок','description':'Моё описание','_locale':'ru'},
            3022:{'id':3022,'name':'Русское блюдо','description':'Описание блюда','_locale':'ru'},
            3372:{'id':3372,'name':'Русский кварц','description':'Описание кварца','_locale':'ru'},
        }
        self.english={
            0:{'id':0,'name':'Tear Balm','description':'Restores HP.','category':'consumable'},
            1200:{'id':1200,'name':'Hien','description':'A light blade.','category':'weapon','kind':'item','type_code':140,'character':0},
            3022:{'id':3022,'name':'Chunky Potato Salad','description':'Restores HP.','category':'food','kind':'item','type_code':980},
            3372:{'id':3372,'name':'Shield 2','description':'Raises ADF.','category':'quartz_normal','kind':'quartz','type_code':200,'element':'water','rarity':'normal'},
        }
        self.cache=config_dir()/'catalog_scanned.json'
        save_catalog_json(self.cache,self.legacy)
        self.pack=self.root/'english.json'
        save_catalog_json(self.pack,self.english)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_every_demo_item_has_verified_offline_art_in_both_languages(self):
        ru,en=demo_catalog()
        for catalog in (ru,en):
            for iid,record in catalog.items():
                with self.subTest(id=iid,name=record['name']):
                    found=original_icon_for_item(iid,record,cache=self.root,manual=self.root)
                    self.assertIsNotNone(found)
                    self.assertTrue(found.verified)
                    self.assertEqual(found.path.parent,resource_path('icons/original'))

    def test_synthetic_save_only_contains_items_in_the_demo_catalog(self):
        catalog,_=demo_catalog()
        saved={entry.item_id for entry in CS3Save(synthetic_demo_save()).items()}
        self.assertLessEqual(saved,catalog.keys())
        self.assertIn(1200,saved)
        self.assertIn(3022,saved)
        self.assertIn(3100,saved)

    def test_import_restores_legacy_icons_without_changing_ru_text_or_cache(self):
        before=self.cache.read_bytes()
        core=EditorCore()
        self.assertIsNone(original_icon_for_item(1200,core.catalog[1200]))
        core.import_english_catalog(self.pack)
        for current in (core,EditorCore()):
            for iid,record in self.legacy.items():
                with self.subTest(id=iid):
                    self.assertEqual(current.item_name(iid),record['name'])
                    self.assertEqual(current.description(iid),record['description'])
                    self.assertEqual(current.catalog[iid]['_locale'],'ru')
                    found=original_icon_for_item(iid,current.catalog[iid])
                    self.assertIsNotNone(found)
                    self.assertTrue(found.verified)
            current.set_language('en')
            self.assertEqual(current.item_name(1200),'Hien')
        self.assertEqual(core.base,self.legacy)
        self.assertEqual(self.cache.read_bytes(),before)

    def test_explicit_metadata_and_overrides_keep_precedence(self):
        core=EditorCore()
        explicit={'kind':'quartz','category':'quartz_normal','type_code':200,
                  'character':44,'element':'mirage','rarity':'sr'}
        core.base[3372].update(explicit)
        core.overrides[1200]={'id':1200,'name':'Мой мастер-кварц','category':'quartz_master'}
        before=copy.deepcopy(core.base)
        core.import_english_catalog(self.pack)
        for key,value in explicit.items():self.assertEqual(core.catalog[3372][key],value)
        self.assertEqual(core.base,before)
        self.assertEqual(core.catalog[1200]['category'],'quartz_master')
        self.assertEqual(core.item_name(1200),'Мой мастер-кварц')
        self.assertIsNone(original_icon_for_item(1200,core.catalog[1200]))

    def test_unidentified_items_still_get_no_guessed_icon(self):
        core=EditorCore()
        self.assertIsNone(original_icon_for_item(1200,core.catalog[1200]))
        for iid,category in ((65534,'other'),(2125,'fish')):
            core.english[iid]={'id':iid,'name':'Unknown item','category':category}
        core.rebuild_catalog()
        for iid in (65534,2125):
            self.assertIsNone(original_icon_for_item(iid,core.catalog[iid]))

    def test_gui_import_replaces_a_cached_missing_icon_and_preserves_pending_input(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from qt_window import MainWindow
        app=QApplication.instance() or QApplication([])
        previous_style=app.style().objectName()
        app.setStyle('Fusion')
        core=EditorCore();core.settings['auto_latest']=False
        source=self.root/'save016.dat';source.write_bytes(synthetic_demo_save())
        original=source.read_bytes();core.open_file(source)
        window=MainWindow(core)
        try:
            window.show();window.show_item(1200);app.processEvents()
            self.assertTrue(window._icon(1200,core.catalog[1200]).isNull())
            window.qty.setValue(7)
            with patch('qt_window.QFileDialog.getOpenFileName',return_value=(str(self.pack),'JSON')):
                window.import_english_dialog()
            app.processEvents()
            self.assertFalse(window._icon(1200,core.catalog[1200]).isNull())
            self.assertTrue(window._icon_sources[1200].verified)
            rows=[window.cat_table.item(row,0) for row in range(window.cat_table.rowCount())]
            row=next(row for row in rows if row.data(Qt.ItemDataRole.UserRole)==1200)
            self.assertFalse(row.icon().isNull())
            self.assertEqual(window.qty.value(),7)
            self.assertTrue(window.has_pending_quantity())
            self.assertFalse(core.save.changed)
            self.assertEqual(source.read_bytes(),original)
        finally:
            window._quantity_user_edited=False
            window.close();window.deleteLater();app.processEvents()
            app.setStyle(previous_style)


if __name__=='__main__':unittest.main()
