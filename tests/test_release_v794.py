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
