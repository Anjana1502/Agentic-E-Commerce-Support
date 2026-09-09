@echo off
rem One-click launcher for the web demo (uses Python 3.12 if available, else python)
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 ui\web.py
    if errorlevel 1 py -3 ui\web.py
) else (
    python ui\web.py
)
pause