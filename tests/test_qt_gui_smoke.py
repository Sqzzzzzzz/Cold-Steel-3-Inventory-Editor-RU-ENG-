"""Optional real Qt smoke tests. Run on Windows with PySide6 installed.

Without PySide6 these tests skip; never claim local Qt integration coverage.
"""
from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from qt_window import MainWindow
except ImportError:
    QApplication=None

from test_v70_release_regressions import synthetic_save
from cs3_save import CS3Save

@unittest.skipIf(QApplication is None,'PySide6 not installed in test environment')
class QtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.tmp.name
        with patch.object(MainWindow,'initial_load',lambda *_:None):
            self.window=MainWindow()
        self.window.core.catalog={
            20:{'id':20,'name':'Тестовый предмет','description':'Описание','category':'consumable'},
            60:{'id':60,'name':'U-материал','description':'Материал','category':'material'},
        }
        self.window.core.save=CS3Save(synthetic_save(((20,2),(60,9))))
        self.window.core.source=Path(self.tmp.name)/'save016.dat'
        self.window.core.source.write_bytes(self.window.core.save.bytes())
        self.window.populate_categories()
        self.window.update_tables()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.core.reset()
        self.window._quantity_user_edited=False;self.window.close()
        self.window.deleteLater()
        if self.old is None:os.environ.pop('APPDATA',None)
        else:os.environ['APPDATA']=self.old
        self.tmp.cleanup()

    def test_navigation_and_language_no_mutation(self):
        initial=self.window.core.save.bytes()
        for view in ('catalog','inventory','tools','catalog'):
            self.window.show_section(view)
            self.app.processEvents()
        self.window.lang.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(self.window.current_section,'catalog')
        self.assertEqual(self.window.core.save.bytes(),initial)
        self.assertEqual(self.window.cat_table.rowCount(),2)

    def test_rendered_edit_and_undo(self):
        self.window.show_section('catalog')
        self.window.show_item(20)
        self.window.qty.setValue(7)
        self.window.apply_single()
        self.assertEqual(self.window.core.save.get_quantity(20),7)
        self.window.undo()
        self.assertEqual(self.window.core.save.get_quantity(20),2)

    def test_save_copy_keeps_original(self):
        self.window.show_item(20)
        self.window.qty.setValue(5)
        self.window.apply_single()
        dst=Path(self.tmp.name)/'edited.dat'
        self.window.core.save_copy(dst)
        self.assertEqual(CS3Save.from_file(dst).get_quantity(20),5)
        self.assertEqual(CS3Save.from_file(self.window.core.source).get_quantity(20),2)
