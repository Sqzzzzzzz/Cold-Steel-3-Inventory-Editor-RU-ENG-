"""Tests of the single game-inspired theme and new three-pane navigation.

All save data is synthetic, never copied from the game.
"""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import Editor
from catalog_visibility import is_visible_item
from cs3_save import CS3Save
from game_scan import load_settings,save_settings
from test_v70_release_regressions import synthetic_save

SAMPLES = {
  60:{'id':60,'name':'U-материал','category':'material','kind':'item','description':'Материал'},
  3200:{'id':3200,'name':'Бригид','category':'quartz_master','kind':'item_q','description':'Тестовый кварц'},
  3201:{'id':3201,'name':'Скульд','category':'quartz_master','kind':'item_q','description':'Тестовый кварц'},
  3202:{'id':3202,'name':'Сириус','category':'quartz_master','kind':'item_q','description':'Тестовый кварц'},
  3809:{'id':3809,'name':'Костюм Альтины','category':'costume','kind':'item','description':'Дополнение','_source':'dlc'},
}

class GameUITests(unittest.TestCase):
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
        self.patchers=[patch.object(Editor,'start_scan',lambda *a,**kw:None),
                       patch.object(Editor,'start_icon_download',lambda *a,**kw:None),
                       patch.object(Editor,'load_latest_save',lambda *a,**kw:None)]
        for x in self.patchers:x.start()
        self.app=Editor()
        self.app.builtin={k:v.copy() for k,v in SAMPLES.items() if k!=3809}
        self.app.scanned_catalog={3809:SAMPLES[3809].copy()}
        self.app._rebuild_catalog()
        self.app._populate_categories()
        self.app._refresh()
        self.app.update_idletasks()

    def tearDown(self):
        try:self.app.destroy()
        finally:
            for x in reversed(self.patchers):x.stop()
            if self.old is None:os.environ.pop('APPDATA',None)
            else:os.environ['APPDATA']=self.old
            self.temp.cleanup()

    def with_save(self):
        self.app.source=Path(self.temp.name)/'save001.dat'
        self.app.save=CS3Save(synthetic_save(((60,3),(3200,1))))
        self.app._refresh()

    def test_has_exactly_three_sections_and_no_light_dark_selector(self):
        self.assertEqual(self.app.page_names,('catalog','inventory','tools'))
        self.assertEqual(len(self.app.tabs.tabs()),3)
        self.assertEqual(set(self.app.nav_buttons),{'catalog','inventory','tools'})
        self.assertFalse(hasattr(self.app,'theme_combo'))
        self.assertEqual(self.app.settings['theme'],'game')

    def test_static_panel_hidden_in_tools_and_restored(self):
        self.app.show_page('tools')
        self.assertEqual(self.app.right_panel.winfo_manager(),'')
        self.app.show_page('inventory')
        self.assertEqual(self.app.right_panel.winfo_manager(),'pack')
        self.app.show_page('catalog')
        self.assertEqual(self.app.right_panel.winfo_manager(),'pack')

    def test_language_switch_keeps_selection_and_item_quantity(self):
        self.with_save()
        self.app.show_page('catalog')
        self.app._select_item(60)
        self.app.qty_var.set('42')
        self.app.language_var.set('English')
        self.app.change_language()
        self.assertEqual(self.app.selected_item,60)
        self.assertEqual(self.app.qty_var.get(),'42')
        self.assertEqual(self.app.nav_buttons['catalog'].cget('text'),'▤  Catalog')
        self.assertEqual(self.app.settings['theme'],'game')
        self.app.language_var.set('Русский')
        self.app.change_language()
        self.assertEqual(self.app.qty_var.get(),'42')

    def test_favorites_persist_across_restart(self):
        self.app.show_page('catalog')
        self.app.all_tree.selection_set('all3200')
        self.app.toggle_favorite()
        self.assertIn(3200,self.app.favorites)
        settings=load_settings()
        self.assertIn(3200,settings['favorites'])
        self.app.active_category='favorites'
        self.app.refresh_catalog()
        self.assertEqual(self.app.all_tree.get_children(),('all3200',))
        self.app.toggle_favorite()
        self.assertNotIn(3200,self.app.favorites)

    def test_recent_ids_and_atomic_single_batch(self):
        self.with_save()
        self.app.show_page('catalog')
        self.app.all_tree.selection_set(('all3200','all3201','all3202'))
        self.app.qty_var.set('7')
        before=self.app.save.bytes()
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.apply_bulk_change()
        for x in (3200,3201,3202):self.assertEqual(self.app.save.get_quantity(x),7)
        self.assertNotEqual(self.app.save.bytes(),before)
        self.assertTrue(set((3200,3201,3202)) <= set(self.app.recents))
        self.app.undo()
        self.assertEqual(self.app.save.bytes(),before)

    def test_remove_multiple_inventory_records_and_undo(self):
        self.with_save()
        self.app.tree.selection_set(('inv60','inv3200'))
        original=self.app.save.bytes()
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.delete_bulk_selected()
        self.assertEqual(self.app.save.occupied_count,0)
        self.app.undo()
        self.assertEqual(self.app.save.bytes(),original)

    def test_add_one_each(self):
        self.with_save()
        self.app.all_tree.selection_set(('all3201','all3202'))
        self.app.qty_var.set('99')
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.add_one_each()
        self.assertEqual(self.app.save.get_quantity(3201),1)
        self.assertEqual(self.app.save.get_quantity(3202),1)

    def test_source_filter_only_known_dlc(self):
        self.app.catalog_source.set('DLC')
        self.app.refresh_catalog()
        self.assertEqual(self.app.all_tree.get_children(),('all3809',))
        self.app.catalog_source.set('Основная игра')
        self.app.refresh_catalog()
        self.assertNotIn('all3809',self.app.all_tree.get_children())
        self.assertIn('all60',self.app.all_tree.get_children())

    def test_presence_filters_are_mutually_exclusive(self):
        self.with_save()
        self.app.only_missing.set(True)
        self.assertFalse(self.app.only_present.get())
        self.assertNotIn('all60',self.app.all_tree.get_children())
        self.app.only_present.set(True)
        self.assertFalse(self.app.only_missing.get())
        self.assertIn('all60',self.app.all_tree.get_children())
        self.assertNotIn('all3202',self.app.all_tree.get_children())

    def test_export_inventory_utf8(self):
        import csv
        self.with_save()
        output=Path(self.temp.name)/'inv.csv'
        with patch('app.filedialog.asksaveasfilename',return_value=str(output)),\
             patch('app.messagebox.showinfo'):
            self.app.export_catalog_csv('inventory')
        with output.open(encoding='utf-8-sig',newline='') as f:
            lines=list(csv.reader(f))
        self.assertEqual(lines[0],['ID','Name','Category','Quantity','Description'])
        self.assertIn('U-материал',lines[1])

    def test_diagnostics_report_and_icon_report_have_content(self):
        report=self.app._diagnostics_text()
        self.assertIn('Видимые: 5',report)
        self.assertIn('Повторяющихся внутренних ID: 0',report)
        with patch.object(self.app,'_show_text') as popup:
            self.app.show_missing_icon_report()
        self.assertTrue(popup.called)

    def test_save_overwrite_ignores_backup_input(self):
        self.with_save()
        self.app.source=Path(self.temp.name)/'save001.dat.bak'
        self.app.save.set_quantity(60,5)
        with patch('app.messagebox.showwarning') as warning:
            self.app.save_overwrite()
        warning.assert_called_once()

class GameSettingsTests(unittest.TestCase):
    def test_migration_to_single_game_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'settings.json'
            save_settings({'theme':'light','language':'ru','favorites':[60],
                           'recents':[3200,60]},file)
            result=load_settings(file)
            self.assertEqual(result['theme'],'game')
            self.assertEqual(result['favorites'],[60])
            self.assertEqual(result['recents'],[3200,60])

if __name__=='__main__':unittest.main()
