@echo off
chcp 65001 > nul
title Dokon Hisobi - 24/7 Telegram Bot va Mini App Server
echo ========================================================
echo  Do'kon Hisobi -- 24/7 Ishlash Rejimi
echo ========================================================

:: Cloudflare HTTPS tunnelni tekshirish
tasklist /fi "imagename eq cloudflared.exe" | find /i "cloudflared.exe" > nul
if errorlevel 1 (
    echo [INFO] Cloudflare HTTPS tunnel ishga tushirilmoqda...
    start /b "" ".\cloudflared.exe" tunnel --url http://127.0.0.1:8080 > cloudflare.log 2>&1
    timeout /t 3 /nobreak > nul
) else (
    echo [INFO] Cloudflare HTTPS tunnel allaqachon ishlab turibdi.
)

:loop
echo.
echo [INFO] Bot va Mini App serveri ishga tushirilmoqda...
.\venv\Scripts\python.exe -u bot.py
echo.
echo [OGOHLANTIRISH] Bot to'xtadi! 3 soniyadan so'ng avtomatik qayta ishga tushiriladi (24/7 himoya)...
timeout /t 3 /nobreak > nul
goto loop
