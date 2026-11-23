@echo off
setlocal
cd /d "%~dp0" || exit /b 1
where py >nul 2>&1
if errorlevel 1 goto usepython
py -3.12 -V >nul 2>&1
if errorlevel 1 goto usepython
py -3.12 scripts\launch.py %*
exit /b %errorlevel%
:usepython
python scripts\launch.py %*
exit /b %errorlevel%
