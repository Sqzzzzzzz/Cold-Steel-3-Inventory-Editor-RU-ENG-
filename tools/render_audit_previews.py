"""Capture the working Qt editor with owner-supplied data, using a private copy."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from catalog_core import parse_item_tbl
from qt_backend import EditorCore
from qt_window import MainWindow
from qt_changes_dialog import ChangesDialog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--table',type=Path,required=True)
    parser.add_argument('--english',type=Path,required=True);parser.add_argument('--save',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'preview');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication([]);app.setStyle('Fusion')
    with tempfile.TemporaryDirectory(prefix='cs3-audit-') as temp,patch.dict(os.environ,{'APPDATA':temp}):
        core=EditorCore();core.settings['auto_latest']=False
        core.base=parse_item_tbl(args.table);core.rebuild_catalog();core.import_english_catalog(args.english)
        source=Path(temp)/args.save.name;shutil.copy2(args.save,source);core.open_file(source)
        w=MainWindow(core);w.resize(1536,864);w.show();app.processEvents()
        def select(iid):
            w.cat_table.clearSelection()
            for row in range(w.cat_table.rowCount()):
                if w.cat_table.item(row,0).data(Qt.ItemDataRole.UserRole)==iid:
                    w.cat_table.selectRow(row);w.cat_table.scrollToItem(w.cat_table.item(row,0));break
        def save(name,widget=None):
            app.processEvents();widget=widget or w
            target=args.output/name;assert widget.grab().save(str(target),'JPEG',95)
            print(name,target.stat().st_size)
        w.filter_group='quartz_master';w.populate_categories();w.update_tables();select(3207)
        save('CS3_v793_16_real_catalog_ru.jpg')
        w.lang.setCurrentIndex(1);save('CS3_v793_17_real_english.jpg')
        w.filter_group='quartz_normal';w.cat_search.setText('Defense');w.populate_categories();w.update_tables();select(3321)
        save('CS3_v793_18_quartz_icons_and_stats.jpg')
        w.qty.setValue(9);w.apply_single();w.notice.hide()
        review=ChangesDialog(w,'copy');review.show();save('CS3_v793_19_real_review_english.jpg',review)
        review.reject();review.deleteLater()
        core.reset();w._quantity_user_edited=False;w.close();w.deleteLater();app.processEvents()


if __name__=='__main__':main()
