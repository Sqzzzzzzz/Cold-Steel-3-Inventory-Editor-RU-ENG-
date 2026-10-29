"""Exercise the packaged executable using disposable, synthetic data only."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import traceback

from app_info import VERSION
from catalog_core import resource_path
from cs3_save import CS3Save, TABLE_OFFSET, TABLE_END
from preview_demo import demo_catalog, synthetic_demo_save
from qt_backend import EditorCore


def run(app, report_path=None):
    checks = []
    result = {'version':VERSION, 'platform':platform.system(), 'frozen':bool(getattr(sys,'frozen',False)), 'checks':checks}
    previous = os.environ.get('APPDATA')
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='cs3-release-check-') as tmp:
            os.environ['APPDATA'] = tmp
            original = synthetic_demo_save()
            source = Path(tmp)/'проверка сохранений/save016.dat'
            source.parent.mkdir()
            source.write_bytes(original)
            core = EditorCore()
            core.settings['auto_latest'] = False
            core.base,core.english = demo_catalog()
            core.rebuild_catalog()
            core.open_file(source)
            core.change({20:7,60:0,3207:2})
            edited = core.save.bytes()
            assert edited[:TABLE_OFFSET] == original[:TABLE_OFFSET]
            assert edited[TABLE_END:] == original[TABLE_END:]
            before = core.save.bytes()
            try:
                core.change({20:8,249:1})
            except ValueError:
                pass
            else:
                raise AssertionError('Unsupported ID 249 was accepted')
            assert core.save.bytes() == before
            checks.append('batch validation is atomic and preserves all non-inventory bytes')
            assert core.undo() and core.save.bytes() == original
            core.change({20:7,60:0,3207:2})
            copy = source.with_name('save016_edited.dat')
            core.save_copy(copy)
            assert CS3Save.from_file(copy).get_quantity(20) == 7
            assert source.read_bytes() == original
            try:
                core.save_copy(copy)
            except FileExistsError:
                pass
            else:
                raise AssertionError('Existing copy was overwritten')
            checks.append('Unicode paths, save copy, no-overwrite and undo work')
            exported=core.export_csv(source.with_suffix('.csv'))
            assert exported.read_bytes().startswith(b'\xef\xbb\xbf')
            assert source.read_bytes()==original
            try:
                core.export_csv(source)
            except ValueError:
                pass
            else:
                raise AssertionError('CSV export accepted the opened save')
            checks.append('CSV export is UTF-8 and cannot overwrite the opened save')
            backup = core.overwrite_with_backup()
            assert backup.read_bytes() == original
            assert CS3Save.from_file(source).bytes() == edited
            assert not core.save.changed
            checks.append('overwrite creates a verified backup and resets the edit baseline')
            manifest = json.loads(resource_path('icons/original/sources.json').read_text('utf-8'))
            assert len(manifest['files']) == 115
            for entry in manifest['files']:
                assert hashlib.sha256(resource_path('icons/original') .joinpath(entry['file']).read_bytes()).hexdigest() == entry['sha256']
            checks.append('all 115 bundled original PNG hashes match the manifest')
            from PySide6.QtGui import QAction
            from PySide6.QtWidgets import QLabel,QAbstractButton
            from qt_window import MainWindow
            window = MainWindow(core)
            window.resize(1536,864)
            window.show()
            window.show_item(3207)
            app.processEvents()
            assert not window.centralWidget()._scaled_wall.isNull()
            assert not window._icon(3207,core.catalog[3207]).isNull()
            assert not window.grab().isNull()
            if report_path:
                Path(report_path).parent.mkdir(parents=True,exist_ok=True)
                assert window.grab().save(str(Path(report_path).parent/'release-ru.png'))
            window.lang.setCurrentIndex(1)
            app.processEvents()
            for obj in window.findChildren(QLabel)+window.findChildren(QAbstractButton)+window.findChildren(QAction):
                if obj in (window.rail_folder,window.save_line):
                    continue  # User-selected Unicode paths are not UI translations.
                text = (obj.text() if hasattr(obj,'text') else '')+' '+obj.toolTip()
                assert not re.search('[А-Яа-яЁё]',text),text
            assert not window.grab().isNull()
            if report_path:
                assert window.grab().save(str(Path(report_path).parent/'release-en.png'))
            assert not core.save.changed
            checks.append('real Qt window renders RU/EN, background and original icons without English UI Cyrillic leaks')
            window.close()
            window.deleteLater()
            app.processEvents()
            window = None
        result['status'] = 'passed'
    except Exception:
        result['status'] = 'failed'
        result['error'] = traceback.format_exc()
    finally:
        if window:
            window.core.reset()
            window._quantity_user_edited = False
            window.close()
        if previous is None:
            os.environ.pop('APPDATA',None)
        else:
            os.environ['APPDATA'] = previous
        if report_path:
            target = Path(report_path)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if result.get('status') == 'passed' else 2
