@echo off
echo ===================================
echo Stream Crossing Model Setup
echo ===================================

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
IF ERRORLEVEL 1 (
    echo.
    echo Failed to create virtual environment.
    echo Make sure Python is installed and added to PATH.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM [CRITICAL FIX] Upgrade build tools to prevent installation errors
echo Upgrading build tools...
python -m pip install --upgrade pip setuptools wheel

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo.
    echo Failed to install dependencies.
    echo Check requirements.txt and your internet connection.
    pause
    exit /b 1
)

echo.
echo Setup complete!
echo.
echo Next steps:
echo    1. Place your input CSV in data\input\
echo    2. In a new terminal:
echo        call venv\Scripts\activate.bat
echo        python src\model.py --input data\input\your_file.csv
echo.
pause