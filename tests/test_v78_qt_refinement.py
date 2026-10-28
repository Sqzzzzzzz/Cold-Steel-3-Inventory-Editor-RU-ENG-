"""Real Qt regression tests for the v7.8 visual shell and safe fallbacks."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qt_window import MainWindow, Backdrop, hud_icon
from cs3_save import CS3Save
from test_v70_release_regressions import synthetic_save


class RefinedHUDQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous_appdata=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.tmp.name
        with patch.object(MainWindow,'initial_load',lambda self:None):
            self.win=MainWindow()
        self.win.core.base={
            60:{'id':60,'name':'U-материал','category':'material','description':'Материал'},
            3207:{'id':3207,'name':'Калейдо','category':'quartz_master','description':'Описание'},
            3357:{'id':3357,'name':'HP 1','category':'quartz_normal','description':'HP'},
        }
        self.win.core.rebuild_catalog()
        self.win.core.save=CS3Save(synthetic_save(((60,5),(3207,1))))
        self.win.core.source=Path(self.tmp.name)/'save016.dat'
        self.win.core.source.write_bytes(self.win.core.save.bytes())
        self.win.populate_categories();self.win.update_tables()
        self.win.show();self.app.processEvents()

    def tearDown(self):
        self.win._quantity_user_edited=False;self.win.close();self.win.deleteLater()
        self.app.processEvents()
        if self.previous_appdata is None:os.environ.pop('APPDATA',None)
        else:os.environ['APPDATA']=self.previous_appdata
        self.tmp.cleanup()

    def test_genuine_qt_backdrop_and_custom_navigation_icons(self):
        self.assertIsInstance(self.win.centralWidget(),Backdrop)
        self.assertFalse(self.win.centralWidget()._scaled_wall.isNull())
        for name in ('catalog','inventory','tools'):
            self.assertFalse(self.win.navigation[name].icon().isNull())
        self.assertFalse(hud_icon('search').isNull())

    def test_category_fallback_icon_not_blank(self):
        self.assertFalse(self.win._icon(60,self.win.core.catalog[60]).isNull())

    def test_minimum_width_preserves_item_column_and_edit_model(self):
        before=self.win.core.save.bytes()
        self.win.resize(1320,760);self.app.processEvents()
        self.assertGreaterEqual(self.win.cat_table.columnWidth(0),175)
        self.assertLessEqual(self.win.cat_tree.width(),205)
        self.assertGreaterEqual(self.win.cat_table.rowCount(),3)
        self.assertEqual(self.win.core.save.bytes(),before)
        self.win.resize(1650,920);self.app.processEvents()
        self.assertEqual(self.win.cat_tree.width(),255)
        self.assertEqual(self.win.detail.width(),416)

    def test_favorite_button_reflects_update_immediately(self):
        self.win.show_item(3207)
        was=3207 in self.win.core.favorites
        self.win.favorite()
        self.assertEqual(3207 in self.win.core.favorites,not was)
        self.assertEqual(self.win.favorite_btn.text(),'★' if not was else '☆')

    def test_language_and_navigation_do_not_change_save(self):
        before=self.win.core.save.bytes()
        self.win.show_item(60)
        self.win.qty.setValue(12)
        self.win.lang.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(self.win.qty.value(),12)
        for section in ('inventory','catalog','tools','catalog'):
            self.win.show_section(section)
            self.app.processEvents()
        self.assertEqual(self.win.core.save.bytes(),before)
