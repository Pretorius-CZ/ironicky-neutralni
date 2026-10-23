@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

echo ============================================
echo  POZOR: tohle SMAZE stare obrazky, videa
echo  i order.json a vse pregeneruje znovu
echo  podle aktualniho quotes.txt.
echo ============================================
pause

echo.
echo Mazou se stare soubory...
del /q order.json 2>nul
if exist out rmdir /s /q out
if exist video rmdir /s /q video

echo.
echo ============================================
echo  1/3  Renderuji obrazky...
echo ============================================
"%PY%" render.py both
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  2/3  Generuji popisky...
echo ============================================
"%PY%" make_captions.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  3/3  Generuji videa (muze trvat 30-60 min)...
echo ============================================
"%PY%" make_video.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  Nahravam na GitHub...
echo ============================================
git add .
git commit -m "remix kategorii + drze"
git push

echo.
echo ============================================
echo  HOTOVO
echo ============================================
pause
exit /b 0

:chyba
echo.
echo ============================================
echo  CHYBA - zkontroluj vystup vyse.
echo ============================================
pause
exit /b 1
