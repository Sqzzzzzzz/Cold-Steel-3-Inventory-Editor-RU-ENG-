"""Regressions confirmed by an independent review of v7.9.5."""
import csv
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from catalog_core import load_catalog_json
from game_scan import ScanResult, config_dir
from preview_demo import synthetic_demo_save, create_demo_window
from qt_backend import EditorCore
from qt_errors import error_text


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path/'profile'))
    core = EditorCore()
    core.base = {20:{'id':20,'name':'Бальзам','description':'Русское описание','_locale':'ru'}}
    core.english = {20:{'id':20,'name':'Tear Balm','description':'Restores HP.','_locale':'en'}}
    core.rebuild_catalog()
    source = tmp_path/'сохранения/save016.dat'
    source.parent.mkdir()
    source.write_bytes(synthetic_demo_save())
    core.open_file(source)
    return core


@pytest.mark.parametrize('language,expected', [('ru','Бальзам'),('en','Tear Balm')])
def test_csv_export_is_utf8_and_keeps_uncommitted_edits(core, tmp_path, language, expected):
    original = core.source.read_bytes()
    core.set_language(language)
    core.change({20:3})
    before = core.save.bytes()
    target = core.export_csv(tmp_path/'inventory')
    assert target.suffix == '.csv'
    assert target.read_bytes().startswith(b'\xef\xbb\xbf')
    with target.open(encoding='utf-8-sig', newline='') as stream:
        rows = {int(r['ID']):r for r in csv.DictReader(stream)}
    assert rows[20] == {'ID':'20','Name':expected,'Qty':'3'}
    assert core.source.read_bytes() == original
    assert core.save.bytes() == before and core.save.changed
    assert core.undo_stack


@pytest.mark.parametrize('kind', ('source','renamed_csv','hardlink'))
def test_csv_cannot_overwrite_open_save_or_its_alias(core, tmp_path, kind):
    if kind == 'renamed_csv':
        renamed = core.source.with_suffix('.csv')
        core.source.rename(renamed)
        core.open_file(renamed)
    target = core.source
    if kind == 'hardlink':
        target = tmp_path/'linked.csv'
        os.link(core.source,target)
    before = core.source.read_bytes()
    with pytest.raises(ValueError, match='opened save'):
        core.export_csv(target)
    assert target.read_bytes() == before
    assert core.source.read_bytes() == before
    assert not core.save.changed


def test_csv_cannot_overwrite_another_dat_file(core, tmp_path):
    target = tmp_path/'save002.dat'
    original = synthetic_demo_save()
    target.write_bytes(original)
    with pytest.raises(ValueError, match='.csv') as error:
        core.export_csv(target)
    assert target.read_bytes() == original
    assert 'выберите файл .csv' in error_text(error.value,'ru')


def test_failed_csv_replacement_leaves_old_file_intact(core, tmp_path):
    target = tmp_path/'inventory.csv'
    target.write_bytes(b'previous CSV')
    with patch('qt_backend.os.replace',side_effect=PermissionError('locked')):
        with pytest.raises(PermissionError):core.export_csv(target)
    assert target.read_bytes() == b'previous CSV'
    assert not list(tmp_path.glob('.cs3-save-*.tmp'))


def test_csv_export_requires_a_save(core, tmp_path):
    core.save = None
    with pytest.raises(RuntimeError):core.export_csv(tmp_path/'inventory.csv')
    assert not (tmp_path/'inventory.csv').exists()


@pytest.mark.parametrize('locale', ('ru',None))
@pytest.mark.parametrize('description', ('◆','Русское описание EP','',None))
def test_english_rescan_retains_neutral_russian_entry_and_persists_it(core, tmp_path, locale, description):
    neutral = {'id':3574,'name':'EP 1','description':description,'kind':'quartz','category':'quartz_normal'}
    if description is None:neutral.pop('description')
    if locale:neutral['_locale'] = locale
    core.base[3574] = neutral
    core.rebuild_catalog()
    scan = ScanResult(tmp_path,files=[tmp_path/'t_item_en.tbl'],items={
        3574:{**neutral,'description':'English quartz description.','_locale':'en'}})
    core.apply_scan_result(scan)
    assert core.item_name(3574) == 'EP 1'
    assert core.base[3574]['description'] == (description or '')
    assert core.description(3574) == (description or 'English quartz description.')
    assert load_catalog_json(config_dir()/'catalog_scanned.json')[3574]['_locale'] == 'ru'
    restarted = EditorCore()
    assert restarted.item_name(3574) == 'EP 1'
    assert restarted.base[3574]['description'] == (description or '')
    assert restarted.description(3574) == (description or 'English quartz description.')
    restarted.set_language('en')
    assert restarted.description(3574) == 'English quartz description.'


def test_english_rescan_updates_explicit_english_records_in_a_mixed_cache(core, tmp_path):
    core.base[3574] = {'id':3574,'name':'EP 1','description':'Old English description.','_locale':'en'}
    core.rebuild_catalog()
    scan = ScanResult(tmp_path,files=[tmp_path/'t_item_en.tbl'],items={
        3574:{'id':3574,'name':'EP 1','description':'Fresh English description.','_locale':'en'}})
    core.apply_scan_result(scan)
    assert core.catalog[3574]['_locale'] == 'en'
    assert core.item_name(3574) == '[EN] EP 1'
    assert core.description(3574) == 'Fresh English description.'


def test_export_dialog_rejects_open_save_without_writing_it():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    window = create_demo_window()
    before = window.core.source.read_bytes()
    try:
        with patch('qt_window.QFileDialog.getSaveFileName',return_value=(str(window.core.source),'CSV')), \
             patch('qt_window.QMessageBox.warning') as warning:
            window.export_csv()
        assert window.core.source.read_bytes() == before
        warning.assert_called_once()
        assert 'Экспорт CSV' in warning.call_args.args[2]
    finally:
        window._quantity_user_edited=False
        window.close();window.deleteLater();app.processEvents();window.core.cleanup()
