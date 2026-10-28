"""Regression coverage for bugs reproduced during the v7.9.3 audit."""
import json
import os
from pathlib import Path
import random
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication,QLabel,QAbstractButton,QMessageBox
from catalog_core import parse_item_tbl,load_catalog_json,save_catalog_json
from catalog_locale import catalog_locale
from cs3_save import CS3Save,TABLE_OFFSET,TABLE_END,RECORD_COUNT
from game_icons import icon_key,quartz_rarity
from game_scan import load_settings
from original_item_icons import original_icon_for_item
from preview_demo import create_demo_window
from qt_backend import EditorCore
from qt_errors import error_text
from test_game_scan import make_realistic_cs3_dlc
from test_v70_release_regressions import synthetic_save


class AuditCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{'APPDATA':self.tmp.name});env.start();self.addCleanup(env.stop)
        self.core=EditorCore();self.source=Path(self.tmp.name)/'сохранения'/ 'save016.dat'
        self.source.parent.mkdir();self.source.write_bytes(synthetic_save(((20,2),(60,8))))
        self.core.open_file(self.source);self.original=self.source.read_bytes()

    def test_boolean_and_float_single_edits_roll_back(self):
        for iid,qty in [(True,2),(20,True),(20,1.5),([],1)]:
            with self.assertRaises(ValueError):self.core.save.set_quantity(iid,qty)
            self.assertEqual(self.core.save.bytes(),self.original)

    def test_randomized_changes_preserve_order_and_all_other_bytes(self):
        rng=random.Random(793);expected={20:2,60:8};save=self.core.save
        for _ in range(100):
            batch={rng.randint(1,200):rng.randint(0,99) for _ in range(12)}
            for iid,qty in batch.items():
                if qty:expected[iid]=qty
                else:expected.pop(iid,None)
            save.set_quantities(batch)
            data=save.bytes()
            self.assertEqual([(e.item_id,e.quantity) for e in CS3Save(data).items()],list(expected.items()))
            self.assertEqual(data[:TABLE_OFFSET],self.original[:TABLE_OFFSET])
            self.assertEqual(data[TABLE_END:],self.original[TABLE_END:])
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_capacity_failure_is_atomic_but_removal_can_free_capacity(self):
        save=CS3Save(synthetic_save(tuple((i,1) for i in range(RECORD_COUNT-16))))
        before=save.bytes()
        with self.assertRaises(ValueError):save.set_quantities({65000:1})
        self.assertEqual(save.bytes(),before)
        save.set_quantities({0:0,65000:1});self.assertEqual(save.occupied_count,RECORD_COUNT-16)

    def test_existing_destination_is_not_overwritten_even_in_publish_race(self):
        if os.name=='nt':self.skipTest('POSIX link publication; Windows rename has native no-replace semantics')
        target=self.source.parent/'copy.dat';publish=os.link
        def racing(src,dst):
            Path(dst).write_bytes(b'another application created this file')
            return publish(src,dst)
        with patch('qt_backend.os.link',side_effect=racing),self.assertRaises(FileExistsError):self.core.save_copy(target)
        self.assertEqual(target.read_bytes(),b'another application created this file')
        self.assertFalse(list(target.parent.glob('.cs3-save-*.tmp')))
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_external_change_during_backup_blocks_commit(self):
        self.core.change({20:8});write=self.core._atomic_write
        external=synthetic_save(((20,77),(60,8)))
        def racing(path,payload,**options):
            Path(path).write_bytes(external)
            return write(path,payload,**options)
        with patch.object(self.core,'_atomic_write',side_effect=racing),self.assertRaises(RuntimeError):self.core.overwrite_with_backup()
        self.assertEqual(self.source.read_bytes(),external)
        backups=list(self.source.parent.glob('*.bak'));self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),self.original)
        self.assertTrue(self.core.save.changed)

    def test_failed_disk_commit_keeps_source_history_and_verified_backup(self):
        self.core.change({20:7});pending=self.core.save.bytes()
        with patch('qt_backend.os.replace',side_effect=PermissionError('locked')),self.assertRaises(PermissionError):self.core.overwrite_with_backup()
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertEqual(self.core.save.bytes(),pending);self.assertTrue(self.core.undo_stack)
        self.assertEqual(next(self.source.parent.glob('*.bak')).read_bytes(),self.original)
        self.assertFalse(list(self.source.parent.glob('.cs3-save-*.tmp')))

    def test_preferences_failure_does_not_hide_successful_edit_or_open(self):
        with patch('qt_backend.save_settings',side_effect=PermissionError('read only')):
            self.core.open_file(self.source);self.core.change({20:8});self.core.toggle_favorite(60)
        self.assertEqual(self.core.quantity(20),8);self.assertIn(60,self.core.favorites)
        self.assertTrue(self.core.persistence_warning);self.assertTrue(self.core.undo())
        self.assertEqual(self.core.save.bytes(),self.original)

    def test_failed_new_file_keeps_previous_open_save_and_history(self):
        self.core.change({20:8});pending=self.core.save.bytes()
        bad=self.source.parent/'bad.dat';bad.write_bytes(b'invalid')
        with self.assertRaises(ValueError):self.core.open_file(bad)
        self.assertEqual(self.core.source,self.source);self.assertEqual(self.core.save.bytes(),pending)
        self.assertTrue(self.core.undo_stack)

    def test_invalid_file_size_is_rejected_before_reading_bytes(self):
        path=self.source.parent/'oversized.dat'
        with path.open('wb') as stream:stream.truncate(32*1024*1024)
        with patch.object(Path,'open',side_effect=AssertionError('must not read oversized save')):
            with self.assertRaises(ValueError):CS3Save.from_file(path)

    def test_changed_file_during_read_is_rejected(self):
        before=self.source.stat()
        after=SimpleNamespace(st_size=before.st_size,st_mtime_ns=before.st_mtime_ns+1)
        with patch.object(Path,'stat',side_effect=[before,after]),self.assertRaises(ValueError):CS3Save.from_file(self.source)

    def test_malformed_catalog_rows_cannot_crash_startup(self):
        target=Path(self.tmp.name)/'CS3InventoryEditor_BETA/catalog_scanned.json'
        for rows in [[4],[{'id':True,'name':'x'}],[{'id':1,'name':'x','category':[]}],
                     [{'id':1,'name':'x','description':[]}]]:
            target.write_text(json.dumps({'items':rows}));core=EditorCore()
            self.assertEqual(core.base,{})

    def test_settings_reject_unicode_digits_and_invalid_ids(self):
        path=Path(self.tmp.name)/'settings.json'
        path.write_text(json.dumps({'favorites':[None,True,{},[],'²','60',60,9999,65536,-1]}))
        self.assertEqual(load_settings(path)['favorites'],[60])

    def test_french_scan_is_not_an_english_catalog(self):
        records={0:{'id':0,'name':'Baume de larme','description':'Un onguent de soins.'}}
        scan=SimpleNamespace(root=self.source.parent,files=[self.source],items=records,errors=[])
        self.core.apply_scan_result(scan);self.assertEqual(self.core.english,{})
        self.assertEqual(catalog_locale(records),'fr')

    def test_english_import_rejects_russian_and_persists_valid_catalog(self):
        p=Path(self.tmp.name)/'english.json'
        save_catalog_json(p,{0:{'id':0,'name':'Целебный бальзам','description':'Русский'}})
        with self.assertRaises(ValueError):self.core.import_english_catalog(p)
        save_catalog_json(p,{0:{'id':0,'name':'Tear Balm','description':'Restores HP.'}})
        self.assertEqual(self.core.import_english_catalog(p),1)
        self.assertEqual(EditorCore().english[0]['name'],'Tear Balm')

    def test_placeholder_descriptions_show_real_native_stats_in_both_languages(self):
        self.core.catalog={3321:{'id':3321,'name':'Defense 2','description':'◆','stats':{'DEF':40}}}
        self.assertEqual(self.core.details_text(3321),'DEF +40')
        self.core.language='en';self.assertEqual(self.core.details_text(3321),'DEF +40')
        self.core.catalog[3321]['stats']={}
        self.assertEqual(self.core.details_text(3321),'No description is available in the loaded catalog.')

    def test_base_english_import_retains_dlc_and_replaces_only_imported_ids(self):
        self.core.base={0:{'id':0,'name':'Бальзам','description':'Русское описание'},
                        3804:{'id':3804,'name':'Костюм','description':'Русское описание','category':'costume'}}
        self.core.english={0:{'id':0,'name':'Old English name','description':'The old description'},
                           3804:{'id':3804,'name':"Juna's Lloyd Costume",'description':'A costume with a familiar design.','category':'costume','_locale':'en','_source':'dlc'}}
        self.core.rebuild_catalog();dlc=dict(self.core.english[3804])
        p=Path(self.tmp.name)/'base_english.json'
        save_catalog_json(p,{0:{'id':0,'name':'Tear Balm','description':'Restores HP.'}})
        self.assertEqual(self.core.import_english_catalog(p),2)
        self.assertEqual(self.core.english[0]['name'],'Tear Balm')
        self.assertEqual(self.core.english[3804],dlc)
        self.assertEqual(EditorCore().english[3804],dlc)
        self.assertEqual(self.core.catalog[0]['name'],'Бальзам')


    def test_unsupported_sepith_addition_is_atomic_and_localized(self):
        before=self.core.save.bytes()
        with self.assertRaises(ValueError) as error:self.core.change({20:3,249:1})
        self.assertEqual(self.core.save.bytes(),before)
        self.assertFalse(self.core.undo_stack)
        self.assertNotRegex(error_text(error.exception,'en'),r'[А-Яа-яЁё]')
        self.assertIn('249',error_text(error.exception,'en'))

    def test_existing_sepith_stack_remains_readable_and_can_be_removed(self):
        original=synthetic_save(((20,2),(249,1),(60,8)))
        self.source.write_bytes(original);self.core.open_file(self.source)
        self.assertEqual(self.core.quantity(249),1)
        self.core.change({20:3})
        self.assertEqual(self.core.quantity(249),1)
        self.core.change({249:0})
        target=self.source.parent/'cleaned_copy.dat';self.core.save_copy(target)
        result=CS3Save.from_file(target)
        self.assertEqual(result.get_quantity(249),0)
        self.assertEqual(result.get_quantity(20),3)
        self.assertEqual(result.bytes()[:TABLE_OFFSET],original[:TABLE_OFFSET])
        self.assertEqual(result.bytes()[TABLE_END:],original[TABLE_END:])
        self.assertEqual(self.source.read_bytes(),original)
        self.assertTrue(self.core.undo());self.assertEqual(self.core.quantity(249),1)

class AuditParserAndIconTests(unittest.TestCase):
    def test_english_contracted_internal_markers_match_russian_visibility(self):
        from catalog_visibility import is_visible_item
        for text in ["◆Doesn't appear on list.",'◆Doesn’t appear on list.','◆Does not appear in the list.']:
            self.assertFalse(is_visible_item({'id':305,'name':'A real book title','description':text}))
        self.assertTrue(is_visible_item({'id':3321,'name':'Defense 2','description':'◆'}))

    def test_cli_audit_uses_bundled_art_and_counts_unverified_ids(self):
        from audit_assets import audit
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'catalog.json'
            save_catalog_json(p,{60:{'id':60,'name':'U-Material','category':'material'},
                                 65000:{'id':65000,'name':'Unknown material','category':'material'}})
            checked,wanted,missing=audit(p,Path(temp)/'empty-cache')
            self.assertEqual(checked,2);self.assertEqual(sum(missing.values()),1)
            self.assertEqual(wanted['U-Material (Sen III Item).png'],1)
            self.assertIn('65000',next(iter(missing)))

    def test_quartz_fixed_prefix_does_not_mistake_stats_for_text_marker(self):
        ordinary=make_realistic_cs3_dlc(3321,'Defense 2',flag='SLZ')
        p=ordinary.index(b'item\0',15)+7;body=bytearray(ordinary[p:])
        at=body.index(0,4)+1;body[at:at+2]=(200).to_bytes(2,'little');body[at+4]=1
        body[at+80:at+82]=b'\xff\xff';body.extend(bytes(12))
        struct.pack_into('<h',body,at+100,40)
        header=struct.pack('<HI',1,1)+b'item_q\0'+struct.pack('<I',1)
        tbl=header+b'item_q\0'+struct.pack('<H',len(body))+body
        row=parse_item_tbl(tbl)[3321]
        self.assertEqual(row['name'],'Defense 2');self.assertEqual(row['element'],'earth')
        self.assertEqual(row['rarity'],'normal')
        self.assertEqual(row['stats'],{'DEF':40})
        self.assertEqual(icon_key(row,3321),'quartz_earth')

    def test_stat_upgrades_keep_normal_icons_and_native_metadata_wins(self):
        self.assertEqual(quartz_rarity(3321,{}),'normal')
        self.assertEqual(quartz_rarity(3337,{}),'normal')
        self.assertEqual(quartz_rarity(3313,{}),'r')
        self.assertEqual(quartz_rarity(3329,{}),'sr')
        self.assertEqual(quartz_rarity(3313,{'rarity':'normal'}),'normal')
        self.assertEqual(icon_key({'category':'quartz_normal'},3390),'quartz_water')

    def test_native_food_types_and_cover_types_work_without_stock_ids(self):
        self.assertEqual(icon_key({'category':'food','type_code':0x03d3},65000),'food_superb')
        self.assertEqual(icon_key({'category':'decoration','type_code':0xc6},65000),'orbment')
        self.assertEqual(icon_key({'category':'decoration','type_code':0xc7},65000),'quest')

    def test_pom_droplet_uses_confirmed_native_feather_in_both_languages(self):
        for name in ('Капля сияющей пом', 'Shining Pom Droplet'):
            record={'id':130,'name':name,'category':'consumable','type_code':0x04e6}
            found=original_icon_for_item(130,record)
            self.assertIsNotNone(found)
            self.assertTrue(found.verified)
            self.assertEqual(found.path.name,'Key (Sen III Item).png')
            self.assertEqual(record['category'],'consumable')
        self.assertIsNone(original_icon_for_item(130,{'category':'quartz_master'}))

    def test_pom_bait_uses_confirmed_native_feather_in_both_languages(self):
        for name in ('Приманка для сияющей пом', 'Shining Pom Bait'):
            record={'id':39,'name':name,'category':'material','type_code':0x0382}
            found=original_icon_for_item(39,record)
            self.assertIsNotNone(found)
            self.assertTrue(found.verified)
            self.assertEqual(found.path.name,'Key (Sen III Item).png')
            self.assertEqual(record['category'],'material')
        self.assertIsNone(original_icon_for_item(39,{'category':'quartz_master'}))

    def test_unknown_items_never_get_an_arbitrary_specific_icon(self):
        for iid,category in [(65000,'weapon'),(65001,'material'),(65002,'quartz_master'),
                             (65003,'quartz_normal'),(65004,'other'),(249,'material'),(2125,'fish')]:
            self.assertIsNone(original_icon_for_item(iid,{'category':category}))

    def test_all_stock_fish_share_the_owner_confirmed_sprite_in_both_languages(self):
        for iid in range(2100,2125):
            for name in ('Рыба','Fish'):
                found=original_icon_for_item(iid,{'id':iid,'name':name,'category':'fish'})
                self.assertIsNotNone(found);self.assertTrue(found.verified)
                self.assertEqual(found.path.name,'Fish L (Sen III Item).png')
        # Reserved records and custom IDs are outside the owner's confirmation.
        for iid in (*range(2125,2130),65000):
            self.assertIsNone(original_icon_for_item(iid,{'id':iid,'name':'Kasagin','category':'fish'}))

    def test_seven_element_sepith_is_not_offered_as_an_inventory_stack(self):
        from catalog_visibility import is_visible_item
        for name in ('Сепит семи элементов','Seven-Element Sepith'):
            self.assertFalse(is_visible_item({'id':249,'name':name,'description':'◆'}))
        # A placeholder description does not invalidate normal items or quartz.
        for iid in (241,248,3321):
            self.assertTrue(is_visible_item({'id':iid,'name':'Real entry','description':'◆'}))
        self.assertTrue(is_visible_item({'id':[],'name':'Custom entry'}))

    def test_all_known_save_errors_have_english_messages(self):
        cases=['Размер 10 байт вместо ожидаемых 1311424. Редактор поддерживает проверенный тип сохранений CS3 NISA для Windows.',
          'Неизвестные данные в записи инвентаря №2; запись отменена',
          'Слот №2 помечен пустым, но содержит количество 7',
          'Недопустимое количество 100 для ID 20, слот 3','Дублирующийся ID 20 — редактор остановлен',
          'ID предмета должен быть числом от 0 до 65535, кроме 9999','Количество должно быть в диапазоне 0–99',
          'Неверный UTF-8 для предмета ID 42','Незавершённые строки TBL, ID 42']
        for message in cases:
            self.assertNotRegex(error_text(message,'en'),r'[А-Яа-яЁё]')


class AuditQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.win=create_demo_window();self.win.show();self.app.processEvents()
    def tearDown(self):
        self.win.core.reset();self.win._quantity_user_edited=False
        self.win.close();self.win.core.cleanup();self.win.deleteLater();self.app.processEvents()

    def test_existing_unsupported_sepith_is_visible_for_removal_only(self):
        w=self.win
        w.core.catalog[249]={'id':249,'name':'Сепит семи элементов','description':'◆','category':'material'}
        w.core.save=CS3Save(synthetic_save(((20,2),(249,1))))
        w.inv_filter_group='material';w.populate_categories();w.show_section('inventory')
        self.assertNotIn(249,w.core.visible())
        self.assertEqual(w.inv_table.rowCount(),1)
        w.inv_table.selectRow(0);self.app.processEvents()
        self.assertEqual(w.active_item_id,249)
        self.assertFalse(w.apply_btn.isEnabled());self.assertFalse(w.qty.isEnabled())
        self.assertTrue(w.delete_btn.isEnabled())
        w.lang.setCurrentIndex(1);self.app.processEvents()
        self.assertNotRegex(w.description.toPlainText(),r'[А-Яа-яЁё]')
        self.assertIn('not supported',w.description.toPlainText())
        w.delete_single();self.assertEqual(w.core.quantity(249),0)

    def test_english_import_preserves_unapplied_quantity_and_selected_id(self):
        w=self.win;w.cat_table.selectRow(7);self.app.processEvents()
        self.assertEqual(w.active_item_id,3207)
        w.qty.setValue(9);self.assertTrue(w.has_pending_quantity())
        before=w.core.save.bytes()
        with patch('qt_window.QFileDialog.getOpenFileName',return_value=('base_english.tbl','')),patch.object(w.core,'import_english_catalog',return_value=1233):
            w.import_english_dialog()
        self.assertEqual(w.active_item_id,3207)
        self.assertEqual(w.qty.value(),9);self.assertTrue(w.has_pending_quantity())
        self.assertEqual(w.core.save.bytes(),before)

    def test_sort_restores_only_selected_item_ids(self):
        w=self.win;w.filter_group='all';w.update_tables();w.cat_table.selectRow(0)
        selected=w.selected_ids(w.cat_table);w.sort_key=('catalog',1,True);w.update_tables()
        self.assertEqual(w.selected_ids(w.cat_table),selected)
        self.assertFalse(w.bulk_bar.isVisible())
        w.apply_bulk(7);self.assertEqual(w.core.quantity(selected[0]),7)
        self.assertEqual(set(w.edit_changes.changes),set(selected))

    def test_filter_cannot_reuse_old_row_selection(self):
        w=self.win;w.filter_group='all';w.update_tables();w.cat_table.selectRow(0)
        w.filter_group='quartz_master';w.update_tables()
        self.assertEqual(w.selected_ids(w.cat_table),[])

    def test_inventory_bulk_bar_clears_after_deleting_selected_rows(self):
        w=self.win;w.show_section('inventory')
        from PySide6.QtCore import QItemSelectionModel
        for row in [0,1]:
            w.inv_table.selectionModel().select(w.inv_table.model().index(row,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
        ids=w.selected_ids(w.inv_table);self.assertTrue(w.inv_bulk_bar.isVisible())
        w.core.change({i:0 for i in ids});w.update_tables()
        self.assertFalse(w.inv_bulk_bar.isVisible());self.assertEqual(w.selected_ids(w.inv_table),[])

    def test_section_change_syncs_card_with_existing_target_selection(self):
        w=self.win;w.show_section('inventory');w.inv_table.selectRow(0)
        wanted=w.selected_ids(w.inv_table)[0]
        w.show_section('catalog');w.show_item(3207);w.show_section('inventory')
        self.assertEqual(w.active_item_id,wanted)

    def test_english_controls_menus_and_tooltips_contain_no_russian(self):
        w=self.win;w.show_item(3207);w.lang.setCurrentIndex(1)
        for section in ['catalog','inventory','tools']:
            w.show_section(section)
            for child in w.findChildren(QLabel)+w.findChildren(QAbstractButton)+w.findChildren(QAction):
                for value in [child.text(),child.toolTip()]:self.assertNotRegex(value,r'[А-Яа-яЁё]',f'{type(child).__name__}: {value}')
        for action in w.source_actions:self.assertNotIn('/',action.text())

    def test_scan_status_retranslates_after_success_and_failure(self):
        w=self.win;w.core.last_scan=SimpleNamespace(files=[Path('t.tbl')],items={20:{}})
        w.lang.setCurrentIndex(1);self.assertEqual(w.scan_state.text(),'Scanned 1 table; 1 item')
        w._scan_error='unreadable';w.lang.setCurrentIndex(0);w.lang.setCurrentIndex(1)
        self.assertNotRegex(w.scan_state.text(),r'[А-Яа-яЁё]');self.assertIn('could not',w.scan_state.text())

    def test_pending_input_is_preserved_by_sort_and_confirmed_before_discard(self):
        w=self.win;w.show_item(3207);w.qty.setValue(9);w.sort_key=('catalog',1,True);w.update_tables()
        self.assertEqual(w.qty.value(),9);self.assertTrue(w.has_pending_quantity())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No) as ask:
            self.assertFalse(w.confirm_dirty());ask.assert_called_once()

    def test_demo_cannot_import_a_catalog_into_user_profile(self):
        with self.assertRaises(RuntimeError):self.win.core.import_english_catalog('x.json')


if __name__=='__main__':unittest.main()
