"""Visual beta regression tests: no stale theme/active timers or ghost search data."""
from pathlib import Path
from unittest.mock import patch
import os
import tempfile
import unittest

from app import Editor
from hud_art import HUDTab, strip
from PIL import Image

class HUDAppearanceTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            probe=tk.Tk();probe.destroy()
        except tk.TclError as exc:
            if 'display' in str(exc).lower():self.skipTest('Legacy Tk UI requires a graphical display')
            raise
        self.temp=tempfile.TemporaryDirectory()
        self.old=os.environ.get('APPDATA')
        os.environ['APPDATA']=self.temp.name
        self.patches=[patch.object(Editor,'start_scan',lambda *a,**kw:None),
                      patch.object(Editor,'start_icon_download',lambda *a,**kw:None),
                      patch.object(Editor,'load_latest_save',lambda *a,**kw:None)]
        for p in self.patches:p.start()
        self.app=Editor()
        self.app.update_idletasks()

    def tearDown(self):
        try:self.app.destroy()
        finally:
            for p in reversed(self.patches):p.stop()
            if self.old is None:os.environ.pop('APPDATA',None)
            else:os.environ['APPDATA']=self.old
            self.temp.cleanup()

    def test_angular_tabs_are_active_live_widgets(self):
        self.assertIsInstance(self.app.mode_buttons['catalog'],HUDTab)
        self.app.show_page('catalog')
        self.assertTrue(self.app.mode_buttons['catalog'].active)
        self.assertFalse(self.app.mode_buttons['inventory'].active)
        self.app.show_page('inventory')
        self.assertTrue(self.app.mode_buttons['inventory'].active)

    def test_single_theme_and_translucent_header(self):
        self.assertEqual(self.app.settings['theme'],'game')
        self.assertTrue(self.app._wall_original.size[0]>=1600)
        layer=strip(self.app._wall_original,1620,105,260,darkness=120)
        self.assertEqual(layer.size,(1620,105))
        self.assertIn(layer.mode,('RGB','RGBA'))

    def test_search_hints_do_not_pollute_search_state(self):
        self.assertEqual(self.app.search_all.get(),'')
        self.assertEqual(self.app.search_inv.get(),'')
        self.app.search_all.set('3200')
        self.assertEqual(self.app.search_all.get(),'3200')
        self.app.search_all.set('')
        self.assertEqual(self.app.search_all.get(),'')

    def test_right_panel_does_not_resize_or_move(self):
        self.app.show_page('catalog')
        self.app.geometry('1350x770+0+0')
        self.app.update_idletasks()
        self.assertEqual(self.app.right_panel.winfo_manager(),'pack')
        self.assertGreaterEqual(self.app.right_panel.winfo_width(),400)
        self.assertTrue(self.app.catalog_search_entry.winfo_viewable())
        self.assertTrue(self.app.all_tree.winfo_viewable())

    def test_language_switch_updates_canvas_tabs_without_reset(self):
        self.app.qty_var.set('27')
        self.app.language_var.set('English')
        self.app.change_language()
        self.assertEqual(self.app.mode_buttons['catalog'].text,'Catalog items')
        self.assertEqual(self.app.qty_var.get(),'27')
        self.assertEqual(self.app.header_canvas.itemcget(self.app._header_subtitle,'text'),'COLD STEEL III  ·  INVENTORY')
        self.app.language_var.set('Русский')
        self.app.change_language()
        self.assertEqual(self.app.mode_buttons['catalog'].text,'Каталог предметов')

if __name__=='__main__':unittest.main()
