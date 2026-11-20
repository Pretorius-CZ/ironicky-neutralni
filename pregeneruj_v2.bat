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
echo  PREGENEROVANI v2 (pozice 30-279)
echo   - nove lepiky (render2.py)
echo   - popisky s uvedenim autora hudby
echo   - videa s hudbou ze slozky music\
echo   - 5 nedelnich prom (hudba promo_music.mp3)
echo  Pozice 1-29 (uz publikovane) se NEMENI.
echo  Muze trvat 1-2 hodiny. Na konci se zepta,
echo  jestli nahrat na GitHub.
echo ============================================
pause

echo Synchronizace s GitHubem...
git pull --no-rebase --no-edit

echo.
echo 1/4  Renderuji lepiky 30-279...
"%PY%" render2.py both --from 30 --to 279
if errorlevel 1 goto chyba

echo.
echo 2/4  Generuji popisky...
"%PY%" make_captions2.py --from 30
if errorlevel 1 goto chyba

echo.
echo 3/4  Generuji videa 30-279 (nejdelsi krok)...
"%PY%" make_video2.py --from 30 --to 279
if errorlevel 1 goto chyba

echo.
echo 4/4  Generuji nedelni proma...
"%PY%" make_promo.py
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  HOTOVO. Zkontroluj par videi ve slozce video\
echo  (napr. ig_030.mp4, fb_031.mp4, promo_story_ig_1.mp4)
echo ============================================
choice /C AN /M "Nahrat zmeny na GitHub (A = ano, N = ne)"
if errorlevel 2 goto konec

git config http.postBuffer 524288000
git add -A
git commit -m "lepiky v2 + hudba Kevin MacLeod (pozice 30-279, proma)"
git push
if errorlevel 1 goto chyba

echo.
echo ============================================
echo  NAHRANO NA GITHUB
echo ============================================
:konec
pause
exit /b 0

:chyba
echo.
echo ============================================
echo  CHYBA - zkontroluj vystup vyse.
echo  Nic nebylo nahrano na GitHub.
echo ============================================
pause
exit /b 1
