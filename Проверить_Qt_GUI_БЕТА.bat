@echo off
setlocal
cd /d "%~dp0"
if not exist ".qt-preview-venv\Scripts\python.exe" (
  echo Run Run_Qt_Preview.bat first.
  pause
  exit /b 1
)
set QT_QPA_PLATFORM=offscreen
set PYTHONPATH=tests
".qt-preview-venv\Scripts\python.exe" -m unittest -v test_v792_first_launch test_v791_improvements test_v790_reference_hud test_qt_gui_smoke test_v783_hud_ui test_v78_qt_refinement test_qt_backend_v76 test_v70_release_regressions test_game_scan test_beta_profile test_v77_hud_regressions test_v785_background
if errorlevel 1 goto failed
echo All Qt and save-engine checks passed.
pause
exit /b 0
:failed
echo Tests failed. Please copy this output.
pause
exit /b 1
