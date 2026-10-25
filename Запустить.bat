@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>nul
    if errorlevel 1 goto no_python
    py -3 app.py
    goto done
)
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>nul
if errorlevel 1 goto no_python
python app.py
goto done
:no_python
echo Python 3.10 or later is required. Get it at https://www.python.org/downloads/
pause
exit /b 1
:done
if errorlevel 1 (
    echo Editor did not start. See error messages above.
    pause
    exit /b 1
)
endlocal
