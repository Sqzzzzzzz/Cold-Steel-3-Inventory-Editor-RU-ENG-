"""Native binding regressions run out of process so a crash stays diagnosable."""
import os
import subprocess
import sys


def test_repeated_qt_painting_does_not_abort_python(tmp_path):
    # PySide6/Shiboken 6.12.0 decrements None on void calls under CPython 3.10.
    # Repeated redraws used to abort the entire test job, without a test failure.
    code = '''
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor
app = QApplication([])
image = QPixmap(32, 32)
painter = QPainter(image)
red = QColor('red')
for _ in range(10000):
    painter.fillRect(0, 0, 32, 32, red)
painter.end()
assert image.toImage().pixelColor(0, 0) == red
print('painting passed')
'''
    result = subprocess.run(
        [sys.executable, '-X', 'faulthandler', '-c', code],
        cwd=tmp_path, env={**os.environ, 'QT_QPA_PLATFORM':'offscreen'},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+'\n'+result.stderr
    assert 'painting passed' in result.stdout
