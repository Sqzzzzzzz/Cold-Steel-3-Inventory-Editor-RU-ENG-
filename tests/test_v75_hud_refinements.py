"""HUD beta regression checks: no cross-filtering of inventory and localization.

No proprietary game data is required. All save files are synthetic test fixtures.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app import Editor
from cs3_save import CS3Save
from i18n import tr
from test_v70_release_regressions import synthetic_save


class RefinedHUDTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            probe=tk.Tk();probe.destroy()
        except tk.TclError as exc:
            if 'display' in str(exc).lower():self.skipTest('Legacy Tk UI requires a graphical display')
            raise
        self.tmp=tempfile.TemporaryDirectory()
        self.old=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.tmp.name
        self.patches=[patch.object(Editor,'start_scan',lambda *a,**kw:None),
                      patch.object(Editor,'start_icon_download',lambda *a,**kw:None),
                      patch.object(Editor,'load_latest_save',lambda *a,**kw:None)]
        for p in self.patches: p.start()
        self.app=Editor()
        self.app.builtin={
          60:{'id':60,'name':'U-материал','category':'material','description':'Материал'},
          3200:{'id':3200,'name':'Бригид','category':'quartz_master','description':'Мастер-кварц'},
          3201:{'id':3201,'name':'Скульд','category':'quartz_master','description':'Мастер-кварц'},
        }
        self.app._rebuild_catalog()
        self.app._populate_categories()
        self.app.update_idletasks()

    def tearDown(self):
        try: self.app.destroy()
        finally:
            for p in reversed(self.patches):p.stop()
            if self.old is None:os.environ.pop('APPDATA',None)
            else:os.environ['APPDATA']=self.old
            self.tmp.cleanup()

    def _open_synthetic(self):
        path=Path(self.tmp.name)/'save016.dat'
        blob=synthetic_save(((60,12),(3200,1),(3201,1)))
        path.write_bytes(blob)
        self.app._accept_save(path,CS3Save(blob))
        return path

    def test_catalog_category_never_hides_owned_inventory_rows(self):
        self._open_synthetic()
        self.app.active_category='quartz_master'
        self.app._populate_categories()
        self.app.refresh_catalog()
        self.app.show_page('inventory')
        self.app.refresh_inventory()
        actual=set(self.app.tree.get_children())
        self.assertEqual(actual,{'inv60','inv3200','inv3201'})
        self.app.active_category='favorites'
        self.app.refresh_inventory()
        self.assertEqual(set(self.app.tree.get_children()),actual)

    def test_sidebar_save_metadata_and_language(self):
        file=self._open_synthetic()
        self.assertEqual(self.app.sidebar_file_var.get(),file.name)
        self.assertIn(str(file.parent),self.app.sidebar_path_var.get())
        self.app.language_var.set('English')
        self.app.change_language()
        self.assertEqual(tr('Файл загружен'),'File loaded')
        self.assertEqual(self.app.sidebar_state_var.get(),'File loaded')
        self.assertEqual(self.app.nav_buttons['inventory'].cget('text'),'◫  Inventory')
        self.app.language_var.set('Русский')
        self.app.change_language()
        self.assertEqual(self.app.sidebar_state_var.get(),'Файл загружен')

    def test_hud_dividers_and_right_panel_at_minimum_size(self):
        self.app.geometry('1350x770+0+0')
        self.app.show_page('catalog')
        self.app.update_idletasks()
        self.assertTrue(self.app._hud_details_rule.winfo_viewable())
        self.assertTrue(self.app._hud_identity_rule.winfo_viewable())
        self.assertGreaterEqual(self.app.right_panel.winfo_width(),400)
        self.assertTrue(self.app.all_tree.winfo_viewable())
        self.assertTrue(self.app.catalog_search_entry.winfo_viewable())

    def test_compact_layout_keeps_description_and_save_commands_visible(self):
        self.app.geometry('1350x770+0+0')
        self.app.show_page('catalog')
        self.app.update_idletasks()
        self.assertTrue(self.app._right_compact)
        self.assertTrue(self.app.details.winfo_viewable())
        self.assertLessEqual(self.app.details.winfo_rooty()+self.app.details.winfo_height(),
                             self.app.right_panel.winfo_rooty()+self.app.right_panel.winfo_height())
        self.assertIn('Записать + копия',self.app.toolbar_buttons['overwrite'].cget('text'))
        for action,button in self.app.toolbar_buttons.items():
            self.assertTrue(button.winfo_viewable(),action)

    def test_language_changes_preserve_unsaved_quantity(self):
        self._open_synthetic()
        self.app.show_page('catalog')
        self.app._select_item(3200)
        self.app.qty_var.set('29')
        self.app.language_var.set('English')
        self.app.change_language()
        self.assertEqual(self.app.qty_var.get(),'29')
        self.app.language_var.set('Русский')
        self.app.change_language()
        self.assertEqual(self.app.qty_var.get(),'29')
        self.assertEqual(self.app.save.get_quantity(3200),1)

if __name__=='__main__':unittest.main()
