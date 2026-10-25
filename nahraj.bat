@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Nahravam na GitHub (může trvat dle velikosti)
echo ============================================
git add .
git commit -m "footer vys (nad IG UI)"
git push

echo.
echo ============================================
echo  HOTOVO
echo ============================================
pause
