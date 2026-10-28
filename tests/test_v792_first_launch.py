"""First-launch navigation and real Qt worker integration with synthetic TBLs."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from qt_window import MainWindow
from cs3_save import CS3Save
from test_game_scan import make_tbl
from test_v70_release_regressions import synthetic_save


class FirstLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'APPDATA':self.tmp.name});self.env.start()
        with patch.object(MainWindow,'initial_load',lambda _:None):self.win=MainWindow()
        self.win.show();self.app.processEvents()

    def tearDown(self):
        if self.win.scan_thread is not None:
            self.win.scan_thread.quit();self.win.scan_thread.wait(2000);self.app.processEvents()
        self.win.core.reset();self.win._quantity_user_edited=False;self.win.close();self.win.deleteLater();self.app.processEvents()
        self.env.stop();self.tmp.cleanup()

    def catalog(self):
        self.win.core.base={20:{'id':20,'name':'Лекарство','category':'consumable','description':'Пример'}}
        self.win.core.rebuild_catalog();self.win.populate_categories();self.win.update_tables();self.app.processEvents()

    def save_fixture(self):
        path=self.root/'save016.dat';path.write_bytes(synthetic_save(((20,2),)))
        return path

    def game_fixture(self,bad=False,partial=False):
        game=self.root/'game';base=game/'data/text/dat_en/t_item_en.tbl';base.parent.mkdir(parents=True,exist_ok=True)
        base.write_bytes(b'broken' if bad else make_tbl(20,'Лекарство'))
        if partial:
            dlc=game/'data/dlc/text/0001/dat_en/t_item.tbl';dlc.parent.mkdir(parents=True,exist_ok=True);dlc.write_bytes(b'bad DLC')
        return game,base

    def wait_scan(self):
        deadline=time.monotonic()+4
        while self.win.scan_thread is not None and time.monotonic()<deadline:
            self.app.processEvents();QTest.qWait(5)
        self.app.processEvents();self.assertIsNone(self.win.scan_thread)

    def test_empty_profile_guides_without_writing_settings_or_save(self):
        settings=dict(self.win.core.settings)
        self.assertIs(self.win.pages.currentWidget(),self.win.startup_page)
        self.assertTrue(self.win.startup_page.auto_button.isEnabled())
        self.assertFalse(self.win.startup_page.open_button.isEnabled())
        self.assertFalse(self.win.btn_savecopy.isEnabled())
        self.assertFalse(self.win.btn_compare.isEnabled())
        self.win.refresh_startup();self.assertEqual(self.win.core.settings,settings)
        self.assertIsNone(self.win.core.save)

    def test_cached_catalog_enables_save_and_reports_real_count(self):
        self.catalog()
        self.assertTrue(self.win.startup_page.open_button.isEnabled())
        self.assertIn('Предметов: 1',self.win.startup_page.catalog_status.text())
        self.assertFalse(self.win.startup_page.progress.isVisible())

    def test_complete_setup_enters_workspace_without_mutating_save(self):
        self.catalog();path=self.save_fixture();original=path.read_bytes()
        self.win.core.open_file(path);self.win.update_tables();self.app.processEvents()
        self.assertIs(self.win.pages.currentWidget(),self.win.catpage)
        self.assertTrue(self.win.detail_shell.isVisible())
        self.assertEqual(self.win.core.save.bytes(),original)

    def test_open_from_welcome_switches_to_inventory_and_cancel_stays_put(self):
        self.catalog();path=self.save_fixture();original=path.read_bytes()
        with patch.object(QFileDialog,'getOpenFileName',return_value=('','')):
            self.win.startup_page.open_button.click()
        self.assertIs(self.win.pages.currentWidget(),self.win.startup_page)
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')):
            self.win.startup_page.open_button.click()
        self.assertEqual(self.win.current_section,'inventory')
        self.assertIs(self.win.pages.currentWidget(),self.win.invpage)
        self.assertFalse(self.win.core.save.changed);self.assertEqual(path.read_bytes(),original)
        self.assertTrue(self.win.btn_savecopy.isEnabled());self.assertTrue(self.win.btn_compare.isEnabled())

    def test_choosing_same_save_again_still_leaves_forced_guide(self):
        self.catalog();path=self.save_fixture();self.win.core.open_file(path);self.win.update_tables()
        self.win.show_startup();self.assertIs(self.win.pages.currentWidget(),self.win.startup_page)
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')):
            self.win.startup_page.open_button.click()
        self.assertIs(self.win.pages.currentWidget(),self.win.invpage)

    def test_browse_is_optional_and_guide_can_be_reopened(self):
        self.win.startup_page.browse_button.click();self.win.update_tables()
        self.assertIs(self.win.pages.currentWidget(),self.win.catpage)
        self.win.show_section('tools');self.assertIs(self.win.pages.currentWidget(),self.win.toolspage)
        self.win.show_startup();self.assertIs(self.win.pages.currentWidget(),self.win.startup_page)

    def test_choose_folder_cancel_does_not_start_scan(self):
        with patch.object(QFileDialog,'getExistingDirectory',return_value=''),patch.object(self.win,'scan_game') as scan:
            self.win.startup_page.folder_button.click();scan.assert_not_called()
        self.assertFalse(self.win._scan_busy)

    def test_missing_game_error_is_inline_and_controls_recover(self):
        with patch('qt_window.find_game_install',return_value=None),patch.object(QMessageBox,'warning') as popup:
            self.win.startup_page.auto_button.click();self.wait_scan();popup.assert_not_called()
        self.assertIn('Автопоиск не нашёл',self.win.startup_page.catalog_status.text())
        self.assertTrue(self.win.startup_page.folder_button.isEnabled())
        self.assertFalse(self.win.startup_page.open_button.isEnabled())
        self.assertTrue(self.win.startup_page.progress.isHidden())

    def test_real_worker_loads_table_and_then_opens_existing_save(self):
        game,base=self.game_fixture();original=base.read_bytes()
        with patch.object(QFileDialog,'getExistingDirectory',return_value=str(game)):
            self.win.startup_page.folder_button.click()
        self.assertTrue(self.win._scan_busy)
        self.assertTrue(self.win.startup_page.progress.isVisible())
        self.assertFalse(self.win.startup_page.auto_button.isEnabled())
        self.wait_scan()
        self.assertEqual(self.win.core.item_name(20),'Лекарство')
        self.assertIn('Предметов: 1',self.win.startup_page.catalog_status.text())
        self.assertTrue(self.win.startup_page.open_button.isEnabled())
        self.assertEqual(base.read_bytes(),original)
        path=self.save_fixture();payload=path.read_bytes()
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')):
            self.win.startup_page.open_button.click()
        self.assertIs(self.win.pages.currentWidget(),self.win.invpage)
        self.assertEqual(self.win.core.save.bytes(),payload)

    def test_bad_tables_do_not_erase_existing_catalog(self):
        self.catalog();before=dict(self.win.core.catalog);game,_=self.game_fixture(bad=True)
        with patch.object(QMessageBox,'warning') as popup:
            self.win.scan_game(game);self.wait_scan();popup.assert_not_called()
        self.assertEqual(self.win.core.catalog,before)
        self.assertIn('Используется загруженный каталог',self.win.startup_page.catalog_status.text())
        self.assertTrue(self.win.startup_page.open_button.isEnabled())

    def test_partial_dlc_error_reports_loaded_count_without_modal(self):
        game,_=self.game_fixture(partial=True)
        with patch.object(QMessageBox,'warning') as popup:
            self.win.scan_game(game);self.wait_scan();popup.assert_not_called()
        self.assertEqual(len(self.win.core.visible()),1)
        self.assertIn('Некоторые таблицы пропущены: 1',self.win.startup_page.catalog_status.text())
        self.assertTrue(self.win.startup_page.open_button.isEnabled())

    def test_icon_diagnostics_recognize_bundled_originals(self):
        self.catalog()
        with patch.object(self.win,'show_report') as report:
            self.win.icon_report()
        self.assertEqual(report.call_args.args[1],[])

    def test_language_and_compact_layout_keep_actions_visible(self):
        self.catalog();self.win.lang.setCurrentIndex(1);self.app.processEvents()
        self.assertEqual(self.win.startup_page.open_button.text(),'Open save file')
        for width,height in [(1536,864),(1280,720),(1320,760)]:
            self.win.resize(width,height);self.app.processEvents()
            page=self.win.startup_page
            self.assertEqual(page.verticalScrollBar().maximum(),0)
            self.assertGreaterEqual(page.catalog_card.width(),460)
            for button in (page.auto_button,page.folder_button,page.open_button,page.browse_button):
                pos=button.mapTo(page.viewport(),QPoint(0,0))
                self.assertGreaterEqual(pos.x(),0);self.assertGreaterEqual(pos.y(),0)
                self.assertLessEqual(pos.x()+button.width(),page.viewport().width())
                self.assertLessEqual(pos.y()+button.height(),page.viewport().height())


if __name__=='__main__':unittest.main()
