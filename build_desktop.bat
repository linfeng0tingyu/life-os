@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"

if exist ".venv\Scripts\python.exe" goto install

where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto try_python
py -3 -m venv ".venv"
if errorlevel 1 goto failed
goto install

:try_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto no_python
python -m venv ".venv"
if errorlevel 1 goto failed

:install
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements-build.txt"
if errorlevel 1 goto failed

".venv\Scripts\python.exe" "scripts\generate_icon.py"
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm "LifeOS.spec"
if errorlevel 1 goto failed

copy /Y "README.md" "dist\LifeOS\README.md" >nul
if errorlevel 1 goto failed
copy /Y "部署与迁移指南.md" "dist\LifeOS\部署与迁移指南.md" >nul
if errorlevel 1 goto failed
copy /Y "CHANGELOG.md" "dist\LifeOS\CHANGELOG.md" >nul
if errorlevel 1 goto failed
copy /Y "LICENSE" "dist\LifeOS\LICENSE" >nul
if errorlevel 1 goto failed

echo.
echo Life OS desktop package is ready: dist\LifeOS\LifeOS.exe
exit /b 0

:no_python
echo Life OS build requires 64-bit Python 3.12 or newer.
goto failed

:failed
echo.
echo Life OS desktop build failed. Review the message above.
exit /b 1
