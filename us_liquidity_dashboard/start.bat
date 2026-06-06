@echo off
chcp 65001 >nul
title US Liquidity Dashboard
cd /d %~dp0

echo ========================================
echo   US Liquidity Dashboard
echo ========================================
echo.

echo [1/2] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [2/2] Starting Streamlit...
echo Browser URL: http://localhost:8501
echo.
python -m streamlit run app.py

pause
