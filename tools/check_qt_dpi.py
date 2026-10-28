"""Exercise Qt's real high-DPI renderer in isolated processes."""
from pathlib import Path
import argparse,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def inspect(factor):
    os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']=str(factor)
    sys.path.insert(0,str(ROOT))
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication
    from preview_demo import create_demo_window
    app=QApplication([]);app.setStyle('Fusion');w=create_demo_window();w.show();app.processEvents()
    rows=[];startup_rows=[]
    try:
        for width,height in [(1536,864),(1320,760),(1280,720)]:
            w.resize(width,height);app.processEvents()
            for section in ('inventory','tools','catalog'):
                w.show_section(section);app.processEvents()
                if section!='tools':
                    assert w.detail_shell.geometry().right()<=width-16
                    assert w.detail.layout().minimumSize().height()<=w.detail.height()
                    fields_bottom=w.qty.mapTo(w.detail,QPoint(0,w.qty.height())).y()
                    note_top=w.quantity_note.mapTo(w.detail,QPoint()).y()
                    assert fields_bottom<=note_top,(fields_bottom,note_top)
                    desc_bottom=w.description.mapTo(w.detail,QPoint(0,w.description.height())).y()
                    assert desc_bottom<=w.detail.height()
            dpr=w.devicePixelRatioF();grab=w.grab()
            assert abs(dpr-float(factor))<.01
            assert abs(grab.width()-round(width*dpr))<=1
            icon=w.big_icon.pixmap()
            assert icon is not None and icon.devicePixelRatioF()>0
            rows.append({'window':[width,height],'image':[grab.width(),grab.height()],
                         'device_pixel_ratio':dpr,'item_icon_pixels':[icon.width(),icon.height()],
                         'item_icon_device_pixel_ratio':icon.devicePixelRatioF()})
        records=dict(w.core.catalog)
        w.core.save=None;w.core.source=None;w._startup_dismissed=False;w._startup_forced=False
        for width,height in [(1536,864),(1320,760),(1280,720)]:
            w.resize(width,height);w.show_section('catalog')
            for state in ('missing','busy','ready','error'):
                w.core.catalog=records if state=='ready' else {}
                w._scan_busy=state=='busy';w._scan_stage='reading'
                w._scan_error='not_found' if state=='error' else ''
                w.update_tables();app.processEvents()
                page=w.startup_page
                assert w.pages.currentWidget() is page
                assert page.verticalScrollBar().maximum()==0
                assert page.catalog_card.width()>=460
                for button in (page.auto_button,page.folder_button,page.open_button,page.browse_button):
                    point=button.mapTo(page.viewport(),QPoint())
                    assert point.x()>=0 and point.y()>=0
                    assert point.x()+button.width()<=page.viewport().width()
                    assert point.y()+button.height()<=page.viewport().height()
                startup_rows.append({'window':[width,height],'state':state,'scroll_maximum':page.verticalScrollBar().maximum()})
        w._scan_busy=False
        print(json.dumps({'factor':factor,'checks':rows,'startup_checks':startup_rows}))
    finally:w.core.reset();w.close();w.core.cleanup()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--factor',type=float)
    parser.add_argument('--report',type=Path,default=ROOT/'QA_DPI_V793.json');args=parser.parse_args()
    if args.factor is not None:inspect(args.factor);return
    reports=[]
    for factor in (1,1.25,1.5):
        run=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--factor',str(factor)],capture_output=True,text=True,check=True)
        reports.append(json.loads(run.stdout))
    args.report.write_text(json.dumps(reports,indent=2),encoding='utf8')
    for report in reports:print(f"Scale {report['factor']}: {len(report['checks'])} workspace sizes and {len(report['startup_checks'])} first-launch states passed")

if __name__=='__main__':main()
