@echo off
rem ============================================================
rem  Build ColorQuantizer.exe (butuh Python + internet sekali saja)
rem  Default: mode FOLDER (onedir) - startup instan.
rem  Mau single-file? Ganti --onedir jadi --onefile di bawah
rem  (trade-off: startup ~2-5 detik karena nge-unpack tiap buka).
rem ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python tidak ditemukan di PATH.
    pause
    exit /b 1
)

echo [!] Install/update PyInstaller...
python -m pip install --disable-pip-version-check pyinstaller

echo [!] Building EXE (bisa makan 1-3 menit)...
python -m PyInstaller --onedir --windowed --name ColorQuantizer ^
    --collect-all tkinterdnd2 ^
    --add-data "fonts;fonts" ^
    --add-data "logo.jpg;." ^
    --distpath dist --workpath build_pyi --specpath . ^
    --noconfirm --clean color_quantizer.py

if errorlevel 1 (
    echo.
    echo [X] Build gagal - lihat pesan di atas.
    pause
    exit /b 1
)

rem bersihkan folder kerja build
if exist build_pyi rmdir /s /q build_pyi
if exist __pycache__ rmdir /s /q __pycache__

echo.
echo [OK] Selesai: dist\ColorQuantizer\ColorQuantizer.exe
echo      Jalankan exe di dalam folder itu (folder lain = dependency).
echo      Mau copy ke PC lain? copy SELURUH folder ColorQuantizer.
pause
