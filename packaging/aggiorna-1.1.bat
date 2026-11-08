@echo off
rem TALeport 1.1.0: installs the new dependencies, runs the tests, builds the installer.
rem Everything is written to packaging\output\update-1.1.0.log
cd /d "%~dp0.."
set LOG=%CD%\packaging\output\update-1.1.0.log
if not exist packaging\output mkdir packaging\output
echo TALeport 1.1.0 - %DATE% %TIME% > "%LOG%"
echo.
echo  TALeport 1.1.0: aggiornamento in corso, non chiudere questa finestra (10-20 minuti).
echo.
echo == 1/4 Dipendenze ==
echo == DEPENDENCIES == >> "%LOG%"
backend\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "backend[dev,build]" >> "%LOG%" 2>&1
echo exit=%ERRORLEVEL% >> "%LOG%"
backend\.venv\Scripts\python.exe -c "import faster_whisper, ctranslate2, imageio_ffmpeg; print('video deps ok', imageio_ffmpeg.get_ffmpeg_exe())" >> "%LOG%" 2>&1
echo == 2/4 Test backend ==
echo == TESTS == >> "%LOG%"
pushd backend
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider >> "%LOG%" 2>&1
echo exit=%ERRORLEVEL% >> "%LOG%"
popd
echo == 3/4 Test interfaccia ==
echo == UI CHECKS == >> "%LOG%"
pushd frontend
call npm run typecheck >> "%LOG%" 2>&1
echo exit=%ERRORLEVEL% >> "%LOG%"
call npx vitest run >> "%LOG%" 2>&1
echo exit=%ERRORLEVEL% >> "%LOG%"
popd
echo == 4/4 Installer ==
echo == BUILD == >> "%LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build.ps1 >> "%LOG%" 2>&1
echo exit=%ERRORLEVEL% >> "%LOG%"
echo == DONE == >> "%LOG%"
echo.
echo  Finito. Puoi chiudere questa finestra.
pause
