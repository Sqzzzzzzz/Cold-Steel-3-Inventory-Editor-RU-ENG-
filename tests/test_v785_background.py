from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class Background784Tests(unittest.TestCase):
    def test_new_background_asset_exists(self):
        bg=ROOT/'assets'/'academy_hud_background.jpg'
        self.assertTrue(bg.is_file())
        self.assertGreater(bg.stat().st_size, 50000)

    def test_version_strings_updated(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from preview_demo import create_demo_window
        from app_info import VERSION
        app=QApplication.instance() or QApplication([])
        window=create_demo_window()
        try:
            self.assertIn(VERSION,window.windowTitle())
            self.assertNotIn('BETA',window.windowTitle())
        finally:
            window.close();window.deleteLater();app.processEvents();window.core.cleanup()

if __name__=='__main__':
    unittest.main()
