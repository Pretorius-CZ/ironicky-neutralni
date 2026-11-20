@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Verze 2: nove citaty se renderuji v novem stylu a s novou hudbou.
REM Puvodni verze skriptu je v aktualizuj_stary.bat.

set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" --version >nul 2>nul
if errorlevel 1 (
  echo CHYBA: Python nenalezen.
  pause
  exit /b 1
)

echo ============================================
echo  Synchronizace s GitHubem...
echo ============================================
git pull --no-rebase --no-edit

echo.
echo 1/3  Renderuji obrazky novych citatu (lepiky v2)...
"%PY%" render2.py missing --from 30
if errorlevel 1 goto chyba

echo.
echo 2/3  Generuji popisky...
"%PY%" make_captions2.py --from 30
if errorlevel 1 goto chyba

echo.
echo 3/3  Generuji videa novych citatu...
"%PY%" make_video2.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  Nahravam na GitHub...
echo ============================================
git add -A
git commit -m "pridany citaty"
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
echo  CHYBA pri generovani - zkontroluj vystup vyse.
echo ============================================
pause
exit /b 1
