@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" --version >nul 2>nul
if errorlevel 1 (
  echo CHYBA: Python nenalezen.
  pause
  exit /b 1
)

echo ============================================
echo  POZOR: smaze ig_/fb_ obrazky a videa
echo  a pregeneruje je s novym footerem (vys).
echo  Muze trvat ~40-50 min. Promo soubory zustanou.
echo ============================================
pause

echo Mazou se stare soubory...
del /q out\ig_*.png out\fb_*.png 2>nul
del /q video\ig_*.mp4 video\fb_*.mp4 2>nul

echo.
echo 1/3 Renderuji obrazky...
"%PY%" render.py both
if errorlevel 1 goto chyba

echo.
echo 2/3 Generuji popisky...
"%PY%" make_captions.py
if errorlevel 1 goto chyba

echo.
echo 3/3 Generuji videa...
"%PY%" make_video.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  HOTOVO - videa pregenerovana.
echo ============================================
pause
exit /b 0

:chyba
echo.
echo CHYBA - zkontroluj vystup vyse.
pause
exit /b 1
