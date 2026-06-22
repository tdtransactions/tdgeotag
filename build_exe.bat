@echo off
echo ============================================
echo   DONG GOI UNG DUNG GEOTAG
echo ============================================
echo.

echo [1/3] Dang kiem tra Python...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Ban can cai dat Python truoc de tien hanh dong goi!
    echo Vui long tai va cai dat Python tu: https://www.python.org/downloads/
    pause
    exit /b
)

echo [2/3] Dang cai dat cac thu vien can thiet...
pip install customtkinter pyinstaller Pillow piexif tkinterdnd2 >nul 2>&1

echo [3/3] Dang tien hanh dong goi ung dung ra file .exe
echo         (Qua trinh nay mat khoang 2-5 phut, vui long doi...)
echo.

REM Xoa ban build cu neu co
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Tim duong dan thu vien tkdnd
for /f "delims=" %%i in ('python -c "import tkinterdnd2; import os; print(os.path.dirname(tkinterdnd2.__file__))"') do set TKDND_PATH=%%i

REM Tim duong dan thu vien customtkinter
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i

REM Dong goi voi PyInstaller
python -m PyInstaller --noconfirm --onedir --windowed --icon="logo.ico" ^
    --name "td geo tag" ^
    --add-data "%TKDND_PATH%;tkinterdnd2" ^
    --add-data "%CTK_PATH%;customtkinter" ^
    --hidden-import "tkinterdnd2" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL" ^
    --hidden-import "piexif" ^
    "app.py"

echo.
echo ============================================
if exist "dist\td geo tag\td geo tag.exe" (
    echo   DONG GOI THANH CONG!
    if exist "logo.ico" (
        copy /Y "logo.ico" "dist\td geo tag\" >nul
    )
    if exist "store_profiles.db" (
        copy /Y "store_profiles.db" "dist\td geo tag\" >nul
    )
    echo.
    echo   File ung dung cua ban nam tai:
    echo   dist\td geo tag\td geo tag.exe
    echo.
    echo   De phat hanh cho nguoi dung:
    echo   1. Copy TOAN BO thu muc "dist\td geo tag" ra noi khac
    echo   2. Nen ^(zip^) lai va gui cho nguoi khac
    echo   3. Ho chi can giai nen va bam vao file "td geo tag.exe" la dung!
    echo ============================================
) else (
    echo   CO LOI XAY RA! Vui long kiem tra lai.
    echo ============================================
)
pause
