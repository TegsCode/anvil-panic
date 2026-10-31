@echo off
REM Build AnvilPanicClassic.exe: one file, no console, game embedded.
REM
REM   desktop\build-classic.bat
REM
REM Needs python + pyinstaller + pywebview:
REM   pip install pyinstaller pywebview
REM
REM The game is taken from ..\play\index.html — that file is the source of truth
REM for both the exe and the APK, so there is never a stale copy in this folder.
setlocal
cd /d "%~dp0"

set BUILD=%TEMP%\anvil_panic_classic_build
set HTML=%~dp0..\play\index.html

if not exist "%HTML%" (
  echo Missing "%HTML%".
  exit /b 1
)

REM Stage it under the name the classic shell asks for (shell.GAME).
if exist "%BUILD%" rmdir /s /q "%BUILD%"
mkdir "%BUILD%" 2>nul
copy /y "%HTML%" "%BUILD%\anvil_panic_classic.html" >nul

pyinstaller --noconfirm --clean --onefile --windowed --name AnvilPanicClassic ^
  --icon "%~dp0anvil.ico" ^
  --add-data "%BUILD%\anvil_panic_classic.html;." ^
  --add-data "%~dp0anvil.ico;." ^
  --collect-all webview --collect-all clr_loader --collect-all pythonnet ^
  --specpath "%BUILD%" --workpath "%BUILD%\work" --distpath "%BUILD%\dist" ^
  "%~dp0anvil_panic_classic_app.py"

if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)

REM The classic shell looks for anvil_panic_classic.html inside its bundle, so
REM ship the play build under that name as well.
mkdir "%~dp0dist" 2>nul
copy /y "%BUILD%\dist\AnvilPanicClassic.exe" "%~dp0dist\AnvilPanicClassic.exe" >nul
if errorlevel 1 (
  echo COPY FAILED
  exit /b 1
)

echo Built %~dp0dist\AnvilPanicClassic.exe
endlocal
