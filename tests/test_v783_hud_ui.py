"""Qt HUD v7.8.3: visual controls are UI-only until apply, state is accurate."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from qt_window import MainWindow
from cs3_save import CS3Save
from test_v70_release_regressions import synthetic_save


class HUD783Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.tmp.name
        with patch.object(MainWindow,'initial_load',lambda _:None):
            self.win=MainWindow()
        self.win.core.base={60:{'id':60,'name':'Test material','category':'material','description':'Material'}}
        self.win.core.rebuild_catalog()
        self.win.core.save=CS3Save(synthetic_save(((60,2),)))
        self.win.core.source=Path(self.tmp.name)/'save001.dat'
        self.win.core.source.write_bytes(self.win.core.save.bytes())
        self.win.populate_categories();self.win.update_tables();self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win.core.reset()  # avoid unsaved-edit confirmation on close
        self.win._quantity_user_edited=False;self.win.close();self.win.deleteLater();self.app.processEvents()
        if self.old is None:os.environ.pop('APPDATA',None)
        else:os.environ['APPDATA']=self.old
        self.tmp.cleanup()

    def test_presets_preview_then_apply(self):
        self.win.show_item(60)
        original=self.win.core.save.bytes()
        self.win.preset_buttons[50].click()
        self.assertEqual(self.win.qty.value(),50)
        self.assertEqual(self.win.core.save.bytes(),original)
        self.win.apply_single()
        self.assertEqual(self.win.core.save.get_quantity(60),50)
        self.assertEqual(self.win.dirty_chip.property('state'),'dirty')
        self.win.undo()
        self.assertEqual(self.win.core.save.get_quantity(60),2)
        self.assertEqual(self.win.dirty_chip.property('state'),'clean')

    def test_bilingual_hud_and_compact_resize(self):
        original=self.win.core.save.bytes()
        self.win.resize(1320,760);self.app.processEvents()
        self.assertIn('Ctrl+O',self.win.btn_open.text())
        self.assertEqual(self.win.main_header.caption,'КАТАЛОГ ПРЕДМЕТОВ')
        self.win.show_section('inventory')
        self.assertEqual(self.win.main_header.caption,'ТЕКУЩИЙ ИНВЕНТАРЬ')
        self.win.show_section('catalog')
        self.win.show_item(60)
        self.win.qty.setValue(10)
        self.win.lang.setCurrentIndex(1)
        self.assertEqual(self.win.qty.value(),10)
        self.assertEqual(self.win.main_header.caption,'ITEM CATALOG')
        self.assertEqual(self.win.qty_preset_caption.text(),'QUICK QUANTITY')
        self.assertIn('Open',self.win.btn_open.text())
        self.assertEqual(self.win.core.save.bytes(),original)

    def test_chip_distinguishes_no_file(self):
        self.win.refresh_save_labels()
        self.assertEqual(self.win.dirty_chip.property('state'),'clean')
        self.win.core.save=None
        self.win.core.source=None
        self.win.refresh_save_labels()
        self.assertEqual(self.win.dirty_chip.property('state'),'empty')
