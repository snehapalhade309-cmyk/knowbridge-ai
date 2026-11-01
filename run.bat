@echo off
title KnowBridge AI - Starting Application
echo ========================================================
echo         KnowBridge AI - Knowledge Handover Platform
echo ========================================================
echo.
echo Starting Flask application server...
echo The website will automatically open in your default browser.
echo Keep this window open while using the website.
echo.

cd /d "%~dp0"
start http://127.0.0.1:5000
python app.py
pause
