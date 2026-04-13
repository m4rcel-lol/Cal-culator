@echo off
setlocal
cd /d "%~dp0"

if not exist "calculator_rpg.py" (
    echo Error: calculator_rpg.py was not found in this folder.
    exit /b 1
)

py -3 calculator_rpg.py
if errorlevel 1 (
    echo Error: Failed to start the game with Python 3.
    echo Make sure Python 3 is installed and the "py" launcher is available.
    exit /b 1
)

endlocal
