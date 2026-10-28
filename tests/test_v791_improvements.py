"""Behavior checks for edit review, favorites, feedback and authentic icons."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from cs3_save import CS3Save
from edit_changes import EditChanges
from original_item_icons import original_icon_for_item
from preview_demo import create_demo_window
from qt_window import MainWindow
from qt_changes_dialog import ChangesDialog
from test_v70_release_regressions import synthetic_save

ROOT=Path(__file__).resolve().parents[1]


class QuantityChangeTests(unittest.TestCase):
    def test_net_changes_reset_and_slot_order_are_distinct(self):
        save=CS3Save(synthetic_save(((20,2),(60,9))))
        original=save.bytes();changes=EditChanges();changes.refresh(save)
        self.assertFalse(changes.changes)
        save.set_quantities({20:5,60:0,420:1});changes.refresh(save)
        self.assertEqual(changes.counts(),{'added':1,'removed':1,'modified':1})
        self.assertEqual((changes.changes[60].before,changes.changes[60].after),(9,0))
        save.reset();changes.refresh(save)
        self.assertFalse(changes.changes);self.assertEqual(save.bytes(),original)
        save.set_quantities({20:0});save.set_quantities({20:2});changes.refresh(save)
        self.assertFalse(changes.changes);self.assertTrue(changes.reordered)

    def test_baseline_moves_after_verified_save_is_reopened(self):
        save=CS3Save(synthetic_save(((20,2),)));changes=EditChanges()
        save.set_quantities({20:7});changes.refresh(save)
        self.assertEqual(changes.changes[20].before,2)
        reopened=CS3Save(save.bytes());changes.refresh(reopened)
        self.assertFalse(changes.changes);self.assertEqual(changes.before[20],7)
        changes.refresh(None);self.assertFalse(changes.before)


class NativeImprovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.win=create_demo_window();self.win.show();self.app.processEvents()

    def tearDown(self):
        self.win.core.reset();self.win._quantity_user_edited=False;self.win.close();self.win.core.cleanup()
        self.win.deleteLater();self.app.processEvents()

    def test_review_includes_hidden_added_removed_and_changed_items(self):
        self.win.core.change({20:0,3204:1,3207:4})
        self.win.update_tables();before=self.win.core.save.bytes()
        dialog=ChangesDialog(self.win,'copy')
        try:
            ids={dialog.table.item(r,0).data(Qt.ItemDataRole.UserRole) for r in range(dialog.table.rowCount())}
            self.assertEqual(ids,{20,3204,3207})
            self.assertEqual(self.win.core.save.bytes(),before)
            dialog.reject();self.assertEqual(self.win.core.save.bytes(),before)
        finally:dialog.deleteLater()

    def test_row_markers_and_card_follow_apply_undo_and_delete(self):
        self.win.show_item(3207);self.win.qty.setValue(5);self.win.apply_single()
        for row in range(self.win.cat_table.rowCount()):
            item=self.win.cat_table.item(row,0)
            if item.data(Qt.ItemDataRole.UserRole)==3207:
                self.assertEqual(item.data(Qt.ItemDataRole.UserRole+1),(1,5));break
        self.assertIn('1',self.win.quantity_note.text());self.assertIn('5',self.win.quantity_note.text())
        self.win.undo();self.assertFalse(self.win.edit_changes.changes)
        self.win.delete_single();self.assertEqual(self.win.qty.value(),0)
        self.assertIn('После записи: 0',self.win.quantity_note.text())

    def test_quick_favorites_ignore_category_and_keep_save_unchanged(self):
        before=self.win.core.save.bytes()
        self.win.core.favorites={3207,3204}
        self.win.filter_group='weapon';self.win.populate_categories();self.win.update_tables()
        self.win.cat_quick_favorite.click()
        self.assertEqual(self.win.cat_table.rowCount(),2)
        self.win.populate_categories();self.win.update_tables()
        self.assertTrue(self.win.cat_favorites_only)
        self.assertEqual(self.win.cat_tree.selectedItems(),[])
        self.win.show_section('inventory');self.win.inv_quick_favorite.click()
        self.assertEqual(self.win.inv_table.rowCount(),1)
        self.assertEqual(self.win.core.save.bytes(),before)
        self.win.cat_quick_favorite.click()
        self.assertEqual(self.win.cat_table.rowCount(),3)

    def test_pending_input_is_reported_and_never_applied_by_review(self):
        self.win.show_item(3207);before=self.win.core.save.bytes()
        self.win.qty.setValue(9);dialog=ChangesDialog(self.win,'copy')
        try:
            self.assertTrue(self.win.has_pending_quantity())
            self.assertIn('ещё не применён',dialog.note.text())
            self.assertEqual(dialog.table.rowCount(),0)
            self.assertEqual(self.win.core.save.bytes(),before)
            self.assertEqual(self.win.qty.value(),9)
        finally:dialog.deleteLater()

    def test_compact_card_has_no_overlap_and_full_long_name_is_available(self):
        self.win.core.catalog[3207]['name']='Очень длинное название мастер-кварца для проверки компактной карточки'
        for width,height in [(1536,864),(1280,720),(1320,760)]:
            self.win.resize(width,height);self.win.show_item(3207);self.app.processEvents()
            fields_bottom=self.win.qty.mapTo(self.win.detail,QPoint(0,self.win.qty.height())).y()
            note_top=self.win.quantity_note.mapTo(self.win.detail,QPoint(0,0)).y()
            self.assertLessEqual(fields_bottom,note_top)
            desc_bottom=self.win.description.mapTo(self.win.detail,QPoint(0,self.win.description.height())).y()
            self.assertLessEqual(desc_bottom,self.win.detail.height())
            self.assertIn('компактной карточки',self.win.item_name.toolTip())
            self.assertEqual(self.win.core.quantity(3207),1)

    def test_toast_disappears_without_touching_data(self):
        before=self.win.core.save.bytes()
        self.win.show_toast('Изменение отменено','Change undone')
        self.assertTrue(self.win.notice.isVisible())
        self.win.notice_timer.timeout.emit();self.assertFalse(self.win.notice.isVisible())
        self.assertEqual(self.win.core.save.bytes(),before)


class SaveReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'APPDATA':self.tmp.name});self.env.start()
        with patch.object(MainWindow,'initial_load',lambda _:None):self.win=MainWindow()
        self.win.core.catalog={20:{'id':20,'name':'Пример','category':'consumable'}}
        self.win.core.save=CS3Save(synthetic_save(((20,2),)))
        self.win.core.source=Path(self.tmp.name)/'save016.dat'
        self.win.core.source.write_bytes(self.win.core.save.bytes())
        self.original=self.win.core.source.read_bytes();self.win.show_item(20)
        self.win.qty.setValue(7);self.win.apply_single()

    def tearDown(self):
        self.win.core.reset();self.win._quantity_user_edited=False;self.win.close();self.win.deleteLater();self.app.processEvents()
        self.env.stop();self.tmp.cleanup()

    def test_cancelled_review_never_opens_destination_or_writes(self):
        with patch.object(self.win,'show_changes',return_value=False) as review,patch.object(QFileDialog,'getSaveFileName') as pick:
            self.win.save_copy_dialog();review.assert_called_once_with('copy');pick.assert_not_called()
        self.assertEqual(self.win.core.source.read_bytes(),self.original)

    def test_accepted_copy_keeps_original_and_confirms_inline(self):
        dest=Path(self.tmp.name)/'copy.dat'
        with patch.object(self.win,'show_changes',return_value=True),patch.object(QFileDialog,'getSaveFileName',return_value=(str(dest),'')),patch.object(QMessageBox,'information') as popup:
            self.win.save_copy_dialog();popup.assert_not_called()
        self.assertEqual(CS3Save.from_file(dest).get_quantity(20),7)
        self.assertEqual(self.win.core.source.read_bytes(),self.original)
        self.assertIn('Копия сохранена',self.win.notice.text());self.assertTrue(self.win.core.save.changed)

    def test_accepted_overwrite_creates_backup_and_clears_markers(self):
        with patch.object(self.win,'show_changes',return_value=True) as review:
            self.win.overwrite_dialog();review.assert_called_once_with('overwrite')
        backups=list(Path(self.tmp.name).glob('*.bak'))
        self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),self.original)
        self.assertEqual(CS3Save.from_file(self.win.core.source).get_quantity(20),7)
        self.assertFalse(self.win.edit_changes.changes);self.assertTrue(self.win.review_button.isHidden())


class AuthenticIconTests(unittest.TestCase):
    def test_every_bundled_image_has_verified_source_and_hash(self):
        manifest=json.loads((ROOT/'icons/original/sources.json').read_text('utf8'))
        self.assertEqual(len(manifest['files']),115)
        # Public releases do not contain the owner's original game packages
        # or private atlas audit report; verify the available provenance metadata
        # and the hashes of the actual bundled PNG files instead.
        atlas_sources={}
        for entry in manifest['files']:
            self.assertNotIn('error',entry)
            if entry.get('source_kind')=='owner_game_package':
                source=entry['native_source']
                for key in ('package','package_sha256','member','member_sha256','atlas'):
                    self.assertTrue(source[key])
                self.assertEqual(entry['source_sha256'],source['member_sha256'])
                package_meta=tuple(source[key] for key in
                                   ('package','package_sha256','member','member_sha256'))
                atlas=source['atlas']
                if atlas in atlas_sources:
                    self.assertEqual(atlas_sources[atlas],package_meta)
                else:
                    atlas_sources[atlas]=package_meta
                x,y,width,height=source['crop_upright_xywh']
                self.assertTrue(0<=x<x+width<=source['size'][0])
                self.assertTrue(0<=y<y+height<=source['size'][1])
                self.assertEqual(entry['dimensions'],[width,height])
            else:
                self.assertTrue(entry['url'].startswith('https://static.wikia.nocookie.net/kiseki/'))
            data=(ROOT/'icons/original'/entry['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])

    def test_exact_bundled_art_wins_over_cached_generic_family(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)
            shutil.copy2(ROOT/'icons/original/Master (Sen III Slot).png',cache/'Master (Sen III Slot).png')
            result=original_icon_for_item(3207,{'category':'quartz_master'},cache=cache)
            self.assertEqual(result.path.name,'Kaleido (Sen III MQ).png');self.assertEqual(result.match,'item')

    def test_missing_art_is_not_replaced_with_generated_picture(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(original_icon_for_item(65534,{'category':'other'},cache=td,bundled=td,manual=td))


if __name__=='__main__':unittest.main()
