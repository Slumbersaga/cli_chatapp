@echo off
REM Last Updated: 2026-01-07
REM Description: Quick start script for Redis Chat CLI

echo.
echo ====================================================
echo Redis CLI Chat Application
echo ====================================================
echo.

REM Check if .env exists
if not exist .env (
    echo Error: .env file not found!
    echo Please make sure .env is configured with your Upstash credentials.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import requests, dotenv, colorama, plyer, google.generativeai, prompt_toolkit" >nul 2>&1
if errorlevel 1 (
    echo Installing missing dependencies...
    pip install -r requirements.txt
) else (
    echo Dependencies are OK.
)

echo Starting Redis Chat...
timeout /t 2 >nul
cls
python chat.py

pause
