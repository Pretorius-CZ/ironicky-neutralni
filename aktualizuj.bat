@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM --- Najdi Python (prednostne ten z DSH, jinak "python" z PATH) ---
set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo CHYBA: Python nebyl nalezen.
  pause
  exit /b 1
)

echo ============================================
echo  Synchronizace s GitHubem...
echo ============================================
git pull --no-rebase --no-edit

echo.
echo ============================================
echo  1/3  Renderuji obrazky (lepiky)...
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
echo  3/3  Generuji videa (muze trvat nekolik minut)...
echo ============================================
"%PY%" make_video.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  Nahravam na GitHub...
echo ============================================
git add .
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
