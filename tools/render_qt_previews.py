"""Reproducible real Qt screenshots with clearly labeled synthetic demo data."""
from pathlib import Path
import argparse
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QApplication
from preview_demo import create_demo_window


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'preview')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication([]);app.setStyle('Fusion')
    w=create_demo_window();w.resize(1536,864);w.show();app.processEvents()
    def select(table,iid):
        table.clearSelection()
        for row in range(table.rowCount()):
            if table.item(row,0).data(Qt.ItemDataRole.UserRole)==iid:
                table.selectRow(row);return
    def save(name,widget=None,scale=1):
        app.processEvents();widget=widget or w
        if scale==1:pix=widget.grab()
        else:
            pix=QPixmap(widget.width()*scale,widget.height()*scale);pix.fill(Qt.GlobalColor.transparent)
            painter=QPainter(pix)
            try:
                painter.scale(scale,scale);widget.render(painter,QPoint(0,0))
            finally:painter.end()
        path=args.output/name
        if not pix.save(str(path),'JPEG',95):raise RuntimeError(f'Could not save {path}')
        print(f'{name}: {pix.width()}x{pix.height()}, {path.stat().st_size} bytes')
    w.core.favorites={3200,3204,3207,3209}
    select(w.cat_table,3207);w.qty.setValue(4);w.apply_single()
    select(w.cat_table,3201);w.delete_single()
    select(w.cat_table,3204);w.qty.setValue(1);w.apply_single()
    select(w.cat_table,3207);w.notice.hide()
    save('CS3_v793_01_catalog.jpg')
    save('CS3_v793_02_item_detail.jpg',w.detail,2)
    from qt_changes_dialog import ChangesDialog
    review=ChangesDialog(w,'copy');review.show();app.processEvents()
    save('CS3_v793_07_changes_review.jpg',review);review.close();review.deleteLater()
    w.cat_quick_favorite.click();select(w.cat_table,3207);w.notice.hide()
    save('CS3_v793_08_favorites.jpg');w.cat_quick_favorite.click()
    w.show_section('inventory');w.inv_filter_group='quartz_master';w.populate_categories();w.update_tables()
    select(w.inv_table,3207);save('CS3_v793_03_inventory.jpg')
    w.show_section('tools');save('CS3_v793_04_tools.jpg')
    w.show_section('catalog');select(w.cat_table,3207);w.lang.setCurrentIndex(1)
    save('CS3_v793_05_english.jpg')
    w.lang.setCurrentIndex(0);w.resize(1320,760);save('CS3_v793_06_compact.jpg')
    w.resize(1536,864);app.processEvents()
    w.show_toast('Изменения применены. Можно проверить их перед записью.',
                 'Changes applied. Review them before saving.')
    save('CS3_v793_09_notification.jpg')
    w.core.reset();w.close();w.core.cleanup()
    return 0

if __name__=='__main__':raise SystemExit(main())
