@echo off
rem ============================================================
rem  Color Quantizer - PS1 Texture Tool
rem  Double-click to launch the application.
rem  You can also drag and drop image files onto this .bat file.
rem ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python was not found in PATH.
    echo     Install Python 3.10+ from https://www.python.org/downloads/
    echo     Make sure to select "Add Python to PATH" during installation.
    pause
    exit /b 1
)

python -c "import PIL, numpy, tkinter" 2>nul
if errorlevel 1 (
    echo [!] Installing Pillow/numpy dependencies...
    python -m pip install --disable-pip-version-check pillow numpy
)

python -c "import tkinterdnd2" 2>nul
if errorlevel 1 (
    echo [!] Installing tkinterdnd2 for drag and drop...
    python -m pip install --disable-pip-version-check tkinterdnd2
)

python color_quantizer.py %*
if errorlevel 1 (
    echo.
    echo [X] The app exited with an error - see the message above.
    pause
)
