import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk
from app import Editor
from game_scan import scan_game_tables, ScanResult
from test_game_scan import make_tbl

class SourceOnlySmokeTests(unittest.TestCase):
    def test_no_original_game_table_bundled(self):
        root=Path(__file__).resolve().parents[1]
        self.assertFalse((root/'catalog_builtin.json').exists())
        self.assertFalse((root/'catalog_english.json').exists())

    def test_game_scan_works_without_bundled_content(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/'game'/'data'/'text'/'dat_en'
            folder.mkdir(parents=True)
            (folder/'t_item_en.tbl').write_bytes(make_tbl(420,'Mock Game Item'))
            result=scan_game_tables(Path(td)/'game')
            self.assertEqual(result.items[420]['name'],'Mock Game Item')

    def test_gui_accepts_scanned_english_item(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'APPDATA':td}):
            try:e=Editor()
            except tk.TclError:self.skipTest('GUI display unavailable')
            try:
                for job in e._startup_jobs:e.after_cancel(job)
                self.assertEqual(len(e.catalog),0)
                records={420:{'id':420,'name':'Mock Game Item','description':'A game item.','category':'armor','kind':'item'}}
                e._scan_events.put(('result',False,ScanResult(Path(td),items=records,base_count=1)))
                e._check_scan_events()
                self.assertIn(420,e.catalog)
                e.language_var.set('English');e.change_language()
                self.assertEqual(e._get_name(420),'Mock Game Item')
            finally:e.destroy()
if __name__=='__main__':unittest.main()
