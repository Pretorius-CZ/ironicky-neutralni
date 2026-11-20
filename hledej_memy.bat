@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\preto\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

REM Pojistka: soubor .env s tokenem nesmi nikdy skoncit na GitHubu
git check-ignore -q .env
if errorlevel 1 (
  echo CHYBA: .env neni v .gitignore - token by se mohl dostat na GitHub. Koncim.
  pause
  exit /b 1
)
if not exist .env (
  echo CHYBA: chybi soubor .env s META_ACCESS_TOKEN a IG_USER_ID.
  pause
  exit /b 1
)

echo ============================================
echo  Hledam viralni memy z uctu v meme_ucty.txt
echo ============================================
"%PY%" hledac_memu.py
pause
