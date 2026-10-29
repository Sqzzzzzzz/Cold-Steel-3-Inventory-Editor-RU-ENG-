"""Failures reproduced while preparing the Qt release."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from game_scan import ScanResult
from preview_demo import create_demo_window
from save_scan import save_directories
from qt_backend import EditorCore


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = create_demo_window()
    w.show()
    w.activateWindow()
    app.processEvents()
    yield w
    w.core.reset()
    w._quantity_user_edited = False
    w.close()
    w.deleteLater()
    app.processEvents()
    w.core.cleanup()


def test_redirected_windows_saved_games_uses_real_known_folder_guid(tmp_path):
    redirected = tmp_path/'Redirected Saved Games'
    expected = redirected/'FALCOM/ed8_psv3'
    expected.mkdir(parents=True)
    key = Mock()
    key.__enter__ = Mock(return_value=key)
    key.__exit__ = Mock(return_value=False)
    def query(handle, name):
        if name != '{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}':
            raise FileNotFoundError(name)
        return str(redirected), 2
    registry = SimpleNamespace(HKEY_CURRENT_USER=1,OpenKey=Mock(return_value=key),QueryValueEx=query)
    with patch.dict('sys.modules', {'winreg':registry}):
        assert expected in save_directories(home=tmp_path/'Home')


def test_search_finds_the_description_displayed_on_the_card(window):
    record = {'id':3438,'name':'Strike 3','description':'◆','kind':'quartz','category':'quartz_normal',
              'generated_description':'Critical rate+9%','generated_description_locale':'en'}
    window.core.catalog[3438] = record
    window.core.english[3438] = record
    window.core.language = window.language = 'en'
    window.filter_group = 'all'
    window.cat_search.setText('Critical rate+9%')
    assert [r[0] for r in window._rows_for('catalog')] == [3438]


def test_scan_refreshes_selected_card_without_losing_typed_quantity(window):
    window.show_item(3207)
    window.qty.setValue(9)
    def update(_result):
        window.core.catalog[3207]['description'] = 'Обновлённое описание из таблицы.'
    window.core.apply_scan_result = update
    result = ScanResult(Path('.'), items=window.core.catalog, files=[Path('t_item.tbl')])
    window.on_scan_result(result)
    assert window.description.toPlainText() == 'Обновлённое описание из таблицы.'
    assert window.qty.value() == 9
    assert window.has_pending_quantity()


@pytest.mark.parametrize('locale', ('ru', None))
def test_neutral_russian_names_are_not_mislabelled_as_english(tmp_path, monkeypatch, locale):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    core = EditorCore()
    ru = {'id':3574, 'name':'EP 1', 'description':'◆', 'kind':'quartz', 'category':'quartz_normal'}
    if locale:
        ru['_locale'] = locale
    core.base = {3574:ru, 20:{'id':20,'name':'Русский предмет','description':'Русское описание'}}
    core.english = {3574:{**ru, '_locale':'en'}}
    core.rebuild_catalog()
    assert core.item_name(3574) == 'EP 1'


def test_explicit_english_name_keeps_its_marker_in_a_mixed_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    core = EditorCore()
    en = {'id':3574,'name':'EP 1','description':'◆','_locale':'en'}
    core.base = {3574:en,20:{'id':20,'name':'Русский предмет','description':'Описание'}}
    core.english = {3574:en}
    core.rebuild_catalog()
    assert core.item_name(3574) == '[EN] EP 1'


def test_category_counts_remain_visible_and_update_after_edits(window):
    def master_node(tree):
        for n in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(n)
            for c in range(parent.childCount()):
                node = parent.child(c)
                if node.data(0, Qt.ItemDataRole.UserRole) == 'quartz_master':
                    return node
        raise AssertionError('Master quartz category is missing')
    window.resize(1280,720)
    for language in (0,1):
        window.lang.setCurrentIndex(language)
        window.populate_categories()
        QApplication.processEvents()
        assert master_node(window.cat_tree).text(1) == '38'
        owned = master_node(window.inv_tree)
        assert owned.text(1) == '11'
        for tree in (window.cat_tree,window.inv_tree):
            node = master_node(tree)
            cell = tree.visualRect(tree.indexFromItem(node,1))
            assert cell.right() <= tree.viewport().width()
            assert tree.fontMetrics().horizontalAdvance(node.text(1)) <= tree.columnWidth(1)-8
    window._apply({3200:0})
    assert master_node(window.inv_tree).text(1) == '10'
    window.undo()
    assert master_node(window.inv_tree).text(1) == '11'
    # A four-digit catalog total must fit too, including native style margins.
    window.core.catalog.update({10000+i:{'id':10000+i,'name':f'Material {i}',
        'category':'material'} for i in range(1000)})
    window.populate_categories()
    QApplication.processEvents()
    tree = window.cat_tree
    assert tree.topLevelItem(0).text(1) == str(len(window.core.visible()))
    assert tree.columnWidth(1) >= tree.sizeHintForColumn(1)


def test_item_field_captions_fit_in_both_languages(window):
    for width,height in ((1536,864),(1320,760),(1280,720)):
        window.resize(width,height)
        for language in (0,1):
            window.lang.setCurrentIndex(language)
            QApplication.processEvents()
            for caption in (window.id_caption,window.qty_caption):
                assert caption.fontMetrics().horizontalAdvance(caption.text()) <= caption.width()
            assert window.id_field.fontMetrics().horizontalAdvance('65535')+16 <= window.id_field.width()
