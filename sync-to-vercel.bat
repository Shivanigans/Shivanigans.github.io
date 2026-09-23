@echo off
setlocal

REM Copies the finished site into the folder Vercel serves, so the two
REM places do not drift apart. Run this straight after run.bat.
REM
REM If you ever move that folder, change the DEST line below.

set "DEST=C:\Users\abigd\walks-from-life"

if not exist "%DEST%" (
  echo.
  echo Cannot find %DEST%
  echo Edit the DEST line inside this file if you moved it.
  echo.
  pause
  exit /b 1
)

echo Copying the site into %DEST%
copy /Y "%~dp0postcards.html"   "%DEST%\index.html"   >nul
copy /Y "%~dp0captions.txt"     "%DEST%\captions.txt" >nul
copy /Y "%~dp0cards\*.webp"     "%DEST%\cards\"       >nul
copy /Y "%~dp0cards\gallery.js" "%DEST%\cards\"       >nul

echo.
echo What changed:
pushd "%DEST%"
git status --short
echo.
echo To put it online, run these three lines:
echo.
echo     cd /d %DEST%
echo     git add -A ^&^& git commit -m "Update the walks"
echo     git push
popd
echo.
pause
