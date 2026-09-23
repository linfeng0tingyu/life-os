@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"

if exist ".venv\Scripts\python.exe" goto bootstrap

where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto try_python
echo Creating local Python environment...
py -3 -m venv ".venv"
if errorlevel 1 goto failed
goto bootstrap

:try_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto no_python
echo Creating local Python environment...
python -m venv ".venv"
if errorlevel 1 goto failed

:bootstrap
".venv\Scripts\python.exe" "scripts\bootstrap.py"
if errorlevel 1 goto failed

if /i "%~1"=="--no-browser" goto run_default_no_browser
if "%~1"=="" goto run_default
if /i "%~2"=="--no-browser" goto run_custom_no_browser
".venv\Scripts\python.exe" "src\app.py" --home "%~f1"
goto finished

:run_custom_no_browser
".venv\Scripts\python.exe" "src\app.py" --home "%~f1" --no-browser
goto finished

:run_default
".venv\Scripts\python.exe" "src\app.py"
goto finished

:run_default_no_browser
".venv\Scripts\python.exe" "src\app.py" --no-browser
goto finished

:no_python
echo Life OS requires 64-bit Python 3.12 or newer.
echo Install Python from https://www.python.org/ and enable the Python launcher or PATH.
goto failed

:failed
echo.
echo Life OS could not start. Review the message above.
pause
exit /b 1

:finished
endlocal
