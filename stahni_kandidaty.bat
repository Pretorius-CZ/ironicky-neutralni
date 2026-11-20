@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

git check-ignore -q kandidati/x.mp4
if errorlevel 1 (
  echo CHYBA: slozka kandidati neni v .gitignore. Koncim.
  pause
  exit /b 1
)
echo Stahuji nahledy a videa kandidatu...
"%PY%" stahni_kandidaty.py
pause
