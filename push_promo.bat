@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Nahravam promo videa na GitHub...
echo ============================================
git add video/promo_story_*.mp4
git commit -m "promo videa"
git push

echo.
echo ============================================
echo  HOTOVO
echo ============================================
pause
