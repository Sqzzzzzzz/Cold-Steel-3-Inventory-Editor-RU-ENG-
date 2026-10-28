"""Capture actual Qt first-launch widgets with clearly marked demo state data."""
from pathlib import Path
import argparse,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from qt_window import MainWindow
from preview_demo import DemoCore

class FirstLaunchPreview(MainWindow):
    def initial_load(self):pass

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'preview');args=parser.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    app=QApplication([]);app.setStyle('Fusion');core=DemoCore()
    records=dict(core.catalog);core.catalog={};core.save=None;core.source=None
    w=FirstLaunchPreview(core);w.show();app.processEvents()
    def save(name):
        app.processEvents();path=args.output/name
        if not w.grab().save(str(path),'JPEG',95):raise RuntimeError(path)
        print(f'{name}: {path.stat().st_size} bytes')
    save('CS3_v793_10_first_launch.jpg')
    # Demonstration of the same stage-driven view exercised with real worker
    # threads and synthetic TBL files in test_v793_first_launch.py.
    w._scan_busy=True;w._scan_stage='reading';w.refresh_startup()
    save('CS3_v793_11_scanning.jpg')
    w._scan_busy=False;core.catalog=records;w.populate_categories();w.update_tables()
    save('CS3_v793_12_catalog_ready.jpg')
    w.lang.setCurrentIndex(1);save('CS3_v793_15_first_launch_english.jpg')
    w.lang.setCurrentIndex(0);w.resize(1280,720);app.processEvents()
    save('CS3_v793_14_first_launch_compact.jpg')
    w.resize(1536,864);core.catalog={};w._scan_error='not_found';w.update_tables()
    save('CS3_v793_13_game_not_found.jpg')
    w.close();core.cleanup()

if __name__=='__main__':main()
