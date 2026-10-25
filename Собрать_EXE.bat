@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 goto failed
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --add-data "icons;icons" --name CS3_Inventory_Editor app.py
if errorlevel 1 goto failed
echo EXE created in dist\CS3_Inventory_Editor.exe
pause
exit /b 0
:failed
echo Build failed. Python 3.10+ or PyInstaller is required.
pause
exit /b 1
