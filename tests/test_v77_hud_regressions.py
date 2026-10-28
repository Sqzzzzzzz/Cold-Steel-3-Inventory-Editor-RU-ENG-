"""Static HUD integration tests runnable without the optional PySide6 runtime."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class HUDReworkTests(unittest.TestCase):
    def test_window_source_parses(self):
        ast.parse((ROOT/'qt_window.py').read_text('utf-8'))

    def test_theme_is_importable_without_qt(self):
        import qt_hud_theme
        qss=qt_hud_theme.HUD_STYLESHEET
        self.assertIn('QTableWidget',qss)
        self.assertIn('QPlainTextEdit#itemDescription',qss)
        self.assertIn('QPushButton',qss)
        self.assertIn('QWidget#titleBar',qss)

    def test_new_glass_and_layout_are_live_widgets(self):
        src=(ROOT/'qt_window.py').read_text('utf-8')+(ROOT/'qt_hud_widgets.py').read_text('utf-8')
        self.assertIn('class GlassPanel(QFrame)',src)
        self.assertIn('QPainterPath()',src)
        self.assertIn('self.pages=QStackedWidget()',src)
        self.assertIn("self.owned_note.setText",src)
        self.assertIn('self.qty.setValue(owned if owned else 1)',src)

    def test_reopen_clears_previous_details(self):
        src=(ROOT/'qt_window.py').read_text('utf-8')
        self.assertIn('self.active_item_id=None\n                self.populate_categories();self.update_tables()\n                self.show_item(None)',src)

    def test_switching_language_preserves_pending_qty(self):
        src=(ROOT/'qt_window.py').read_text('utf-8')
        self.assertIn('pending_quantity = self.qty.value()', src)
        self.assertIn('self.qty.setValue(pending_quantity)', src)

    def test_windows_build_packs_artwork(self):
        script=(ROOT/'Build_Qt_Preview_EXE.bat').read_text('utf-8')
        self.assertIn('--add-data "assets;assets"',script)
        self.assertIn('qt_window.py',script)
        self.assertTrue((ROOT/'assets'/'academy_hud_background.jpg').is_file())

if __name__=='__main__':unittest.main()
