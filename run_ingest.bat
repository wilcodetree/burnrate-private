@echo off
:: BurnRate automatic JSONL ingestion runner
:: Drop into Windows Task Scheduler for daily / weekly runs.
::
:: Task Scheduler setup:
::   Action:    Start a program
::   Program:   cmd.exe
::   Arguments: /c "C:\dev\BurnRate\run_ingest.bat"
::   Trigger:   Daily at 08:00
::
:: db/ write strategy:
::   Ingest writes to LOCAL_DB (%LOCALAPPDATA%\BurnRate\db) â€” no OneDrive/FUSE race.
::   After render, sync_to_onedrive.py copies key files to OneDrive db/ for sandbox reads.
::   Sandbox never writes sessions.json or ingest_state.json.
::   Sandbox writes claude_ai_tracking.json (snapshot only).
::
:: Log -> BurnRate\db\ingest_log.txt (last 500 lines kept, stays on OneDrive)

setlocal

set "BURNRATE_DIR=C:\dev\BurnRate"
set "PYTHON=python"
:: For venv: set "PYTHON=C:\Users\WilcoDeTree\.venvs\burnrate\Scripts\python.exe"

set "LOCAL_DB=%LOCALAPPDATA%\BurnRate\db"
set "LOG=%BURNRATE_DIR%\db\ingest_log.txt"
set "JSONL_BASE=%USERPROFILE%\.claude\projects"
set "JSONL_PREFIX=C--dev"
:: Cowork (Store app) virtualises AppData\Roaming inside:
:: %LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\local-agent-mode-sessions
:: Step 1b handles that path.
set "JSONL_MIRROR=%BURNRATE_DIR%\_jsonl_mirror"
set "TIMESTAMP=%DATE% %TIME%"

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo [%TIMESTAMP%] BurnRate ingest started >> "%LOG%"
echo [%TIMESTAMP%] LOCAL_DB=%LOCAL_DB% >> "%LOG%"
echo ============================================================ >> "%LOG%"

:: Step 0a â€” ensure local db dir exists
if not exist "%LOCAL_DB%" mkdir "%LOCAL_DB%"

:: Step 0b â€” sync read-side files OneDrive -> local before ingest
:: ingest_state.json: picks up any mtime resets done by sandbox (recovery)
if exist "%BURNRATE_DIR%\db\ingest_state.json" copy /Y "%BURNRATE_DIR%\db\ingest_state.json" "%LOCAL_DB%\ingest_state.json" > nul
:: claude_ai_tracking.json: owned by sandbox; render reads it
if exist "%BURNRATE_DIR%\db\claude_ai_tracking.json" copy /Y "%BURNRATE_DIR%\db\claude_ai_tracking.json" "%LOCAL_DB%\claude_ai_tracking.json" > nul
:: api files: render reads these
if exist "%BURNRATE_DIR%\db\api_daily.json" copy /Y "%BURNRATE_DIR%\db\api_daily.json" "%LOCAL_DB%\api_daily.json" > nul
if exist "%BURNRATE_DIR%\db\api_summary.json" copy /Y "%BURNRATE_DIR%\db\api_summary.json" "%LOCAL_DB%\api_summary.json" > nul
echo [%TIMESTAMP%] OneDrive to local sync done >> "%LOG%"

:: Step 1 â€” mirror JSONL files
:: 1a: Claude Code CLI sessions â€” writes to %USERPROFILE%\.claude\projects\
if not exist "%JSONL_MIRROR%" mkdir "%JSONL_MIRROR%"
powershell -Command "Get-ChildItem -Path '%JSONL_BASE%\%JSONL_PREFIX%*' -Filter '*.jsonl' -Recurse -ErrorAction SilentlyContinue | Copy-Item -Destination '%JSONL_MIRROR%' -Force -ErrorAction SilentlyContinue" >> "%LOG%" 2>&1
:: 1b: Cowork (desktop app) sessions â€” Store app virtualises AppData\Roaming inside:
::     %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions
::     JSONL files are at: ...\outputs\.claude\projects\*\*.jsonl
powershell -Command "Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions') -Filter '*.jsonl' -Recurse -ErrorAction SilentlyContinue | Copy-Item -Destination '%JSONL_MIRROR%' -Force -ErrorAction SilentlyContinue" >> "%LOG%" 2>&1
echo [%TIMESTAMP%] JSONL mirror sync done >> "%LOG%"

cd /d "%BURNRATE_DIR%"

:: Steps 2-5 â€” all write to local db
"%PYTHON%" src\cowork_estimator.py --db-dir "%LOCAL_DB%" ingest >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: ingest failed >> "%LOG%" & exit /b %ERRORLEVEL% )

"%PYTHON%" src\cowork_estimator.py --db-dir "%LOCAL_DB%" rollup >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: rollup failed >> "%LOG%" & exit /b %ERRORLEVEL% )

"%PYTHON%" src\cowork_estimator.py --db-dir "%LOCAL_DB%" forecast >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: forecast failed >> "%LOG%" & exit /b %ERRORLEVEL% )

"%PYTHON%" src\cowork_estimator.py --db-dir "%LOCAL_DB%" render >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: render failed >> "%LOG%" & exit /b %ERRORLEVEL% )

:: Step 6 â€” Python copies local db -> OneDrive (handles paths with spaces reliably)
echo [%TIMESTAMP%] Syncing local db to OneDrive... >> "%LOG%"
"%PYTHON%" src\sync_to_onedrive.py "%LOCAL_DB%" "%BURNRATE_DIR%\db" >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: sync failed >> "%LOG%" & exit /b %ERRORLEVEL% )

echo [%TIMESTAMP%] BurnRate ingest completed successfully >> "%LOG%"

:: Keep last 500 lines of log
powershell -Command "Get-Content '%LOG%' -Tail 500 | Set-Content '%LOG%.tmp'; Move-Item -Force '%LOG%.tmp' '%LOG%'"

endlocal
