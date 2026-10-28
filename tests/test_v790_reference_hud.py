"""Behavior regressions for the rebuilt Qt shell; synthetic saves only."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import QApplication
from preview_demo import create_demo_window, DemoCore


class ReferenceHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.win=create_demo_window();self.win.show();self.app.processEvents()

    def tearDown(self):
        self.win.core.reset();self.win._quantity_user_edited=False;self.win.close();self.win.core.cleanup()
        self.win.deleteLater();self.app.processEvents()

    def test_resize_and_navigation_preserve_bounds_and_pending_quantity(self):
        original=self.win.core.save.bytes();self.win.qty.setValue(17)
        for width,height in [(1536,864),(1320,760),(1650,920),(1280,720),(1536,864)]:
            self.win.resize(width,height);self.app.processEvents()
            for section in ('tools','inventory','catalog'):
                self.win.show_section(section);self.app.processEvents()
                if section!='tools':
                    self.assertLessEqual(self.win.detail_shell.geometry().right(),width-16)
                    self.assertGreaterEqual(self.win.description.height(),110)
                    self.assertGreaterEqual(self.win.cat_table.columnWidth(0),175)
                    self.assertTrue(self.win.detail.rect().contains(self.win.apply_btn.geometry()))
                self.assertEqual(self.win.qty.value(),17)
        self.assertEqual(self.win.core.save.bytes(),original)

    def test_catalog_and_inventory_filters_are_independent(self):
        self.win.filter_group='weapon';self.win.update_tables()
        self.win.show_section('inventory')
        self.assertEqual(self.win.inv_table.rowCount(),self.win.core.save.occupied_count)
        self.win.inv_filter_group='quartz_master';self.win.update_tables()
        ids=self.win.selected_ids(self.win.inv_table)
        self.assertEqual(len(ids),0)
        self.assertEqual(self.win.inv_table.rowCount(),11)
        self.win.show_section('catalog')
        self.assertEqual(self.win.cat_table.rowCount(),3)

    def test_bulk_actions_appear_for_multiple_rows_and_wait_for_apply(self):
        before=self.win.core.save.bytes();table=self.win.cat_table
        table.clearSelection()
        for row in (0,1):
            table.selectionModel().select(table.model().index(row,0),
                QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
        self.app.processEvents()
        self.assertTrue(self.win.bulk_bar.isVisible())
        self.assertEqual(self.win.core.save.bytes(),before)
        self.win.qty.setValue(9);self.win.apply_bulk()
        self.assertEqual(self.win.core.quantity(3200),9)
        self.assertEqual(self.win.core.quantity(3201),9)
        self.win.undo();self.assertEqual(self.win.core.save.bytes(),before)

    def test_language_change_keeps_inventory_filter_and_pending_edit(self):
        original=self.win.core.save.bytes()
        self.win.show_section('inventory');self.win.inv_filter_group='quartz_master'
        self.win.populate_categories();self.win.update_tables();self.win.show_item(3207)
        self.win.qty.setValue(23);self.win.lang.setCurrentIndex(1);self.app.processEvents()
        self.assertEqual(self.win.qty.value(),23)
        self.assertEqual(self.win.inv_table.rowCount(),11)
        self.assertEqual(self.win.item_name.text(),'Kaleido')
        self.assertEqual(self.win.core.save.bytes(),original)


class DemoIsolation(unittest.TestCase):
    def test_preview_never_writes_user_profile_or_exports_synthetic_save(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'APPDATA':td}):
            core=DemoCore()
            try:
                core.change({3207:5});core.set_language('en');core.toggle_favorite(3207)
                with self.assertRaises(RuntimeError):core.save_copy(Path(td)/'save001.dat')
                with self.assertRaises(RuntimeError):core.overwrite_with_backup()
                self.assertEqual(list(Path(td).iterdir()),[])
            finally:core.cleanup()


if __name__=='__main__':unittest.main()
