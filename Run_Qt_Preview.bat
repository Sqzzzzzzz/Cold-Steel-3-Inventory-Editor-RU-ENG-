@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto no_python
py -3 -c "import sys; sys.exit(sys.version_info < (3,10))"
if errorlevel 1 goto no_python
if not exist ".qt-preview-venv\Scripts\python.exe" (
  py -3 -m venv ".qt-preview-venv"
  if errorlevel 1 goto failed
)
call ".qt-preview-venv\Scripts\activate.bat"
python -m pip install -r requirements-qt.txt
if errorlevel 1 goto failed
python qt_window.py %*
if errorlevel 1 goto failed
exit /b 0
:no_python
echo Python 3.10 or later is required.
pause
exit /b 1
:failed
echo Qt Preview could not run. Please send the error log from this window.
pause
exit /b 1
