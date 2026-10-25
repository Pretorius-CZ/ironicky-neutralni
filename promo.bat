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
echo  Generuji promo:
echo   - 8 uvodu (stridave)
echo   - 5 CTA variant
echo   - nahodne lepiky
echo   - IG i FB
echo  Muze trvat 5-10 min.
echo ============================================
pause

echo Generuji uvodni karty...
"%PY%" make_intro.py
if errorlevel 1 goto chyba

echo.
echo Generuji proma...
"%PY%" make_promo.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  HOTOVO - proma ve video/
echo  (promo_story_ig_1..5.mp4, promo_story_fb_1..5.mp4)
echo ============================================
pause
exit /b 0

:chyba
echo.
echo CHYBA - zkontroluj vystup vyse.
pause
exit /b 1
