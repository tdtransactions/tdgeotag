@echo off
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python chua duoc cai dat tren may tinh nay.
    echo Vui long tai va cai dat Python tu: https://www.python.org/downloads/
    echo Khi cai dat, nho tich vao o "Add python.exe to PATH".
    pause
    exit /b
)

echo Dang cai dat thu vien...
pip install customtkinter Pillow piexif tkinterdnd2 >nul 2>&1

echo Dang chay ung dung...
python app.py
pause
