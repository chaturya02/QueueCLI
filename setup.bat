@echo off
REM QueueCTL Setup Script for Windows

echo ============================================
echo QueueCTL Setup Script
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

echo [1/4] Python found
python --version

echo.
echo [2/4] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo.
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [4/4] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [5/5] Installing QueueCTL...
pip install -e .
if %errorlevel% neq 0 (
    echo ERROR: Failed to install QueueCTL
    pause
    exit /b 1
)

echo.
echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo To get started:
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate
echo.
echo   2. Run the demo:
echo      python demo.py
echo.
echo   3. Or start using QueueCTL:
echo      queuectl --help
echo.
echo See QUICKSTART.md for more information.
echo.
pause
