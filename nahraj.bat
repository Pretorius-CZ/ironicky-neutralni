@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Nahravam na GitHub (muze trvat dle velikosti)
echo ============================================
git add .
git commit -m "footer vys (nad IG UI)"
git pull --no-rebase --no-edit
git push

echo.
echo ============================================
echo  HOTOVO
echo ============================================
pause
