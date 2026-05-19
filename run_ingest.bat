@echo off
:: BurnRate automatic JSONL ingestion runner
:: Drop into Windows Task Scheduler for daily / weekly runs.
::
:: Task Scheduler setup:
::   Action:    Start a program
::   Program:   cmd.exe
::   Arguments: /c "C:\Users\WilcoDeTree\OneDrive - Valona Intelligence\Claude Cowork Output\BurnRate\run_ingest.bat"
::   Trigger:   Daily at 08:00
::
:: Logs -> BurnRate\db\ingest_log.txt (last 500 lines kept)

setlocal

set BURNRATE_DIR=C:\Users\WilcoDeTree\OneDrive - Valona Intelligence\Claude Cowork Output\BurnRate
set PYTHON=python
:: For venv: set PYTHON=C:\Users\WilcoDeTree\.venvs\burnrate\Scripts\python.exe

set LOG=%BURNRATE_DIR%\db\ingest_log.txt
set TIMESTAMP=%DATE% %TIME%

set JSONL_SRC=%USERPROFILE%\.claude\projects\C--Users-WilcoDeTree-OneDrive---Valona-Intelligence-Claude-Cowork-Output
set JSONL_MIRROR=%BURNRATE_DIR%\_jsonl_mirror

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo [%TIMESTAMP%] BurnRate ingest started >> "%LOG%"
echo ============================================================ >> "%LOG%"

:: Step 0 — mirror JSONL files from ~/.claude/projects into a mountable folder
if not exist "%JSONL_MIRROR%" mkdir "%JSONL_MIRROR%"
powershell -Command "Copy-Item -Path '%JSONL_SRC%\*.jsonl' -Destination '%JSONL_MIRROR%' -Force -ErrorAction SilentlyContinue" >> "%LOG%" 2>&1
echo [%TIMESTAMP%] JSONL mirror sync done >> "%LOG%"

cd /d "%BURNRATE_DIR%"

%PYTHON% src\cowork_estimator.py ingest >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: ingest failed >> "%LOG%" & exit /b %ERRORLEVEL% )

%PYTHON% src\cowork_estimator.py rollup >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: rollup failed >> "%LOG%" & exit /b %ERRORLEVEL% )

%PYTHON% src\cowork_estimator.py forecast >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: forecast failed >> "%LOG%" & exit /b %ERRORLEVEL% )

%PYTHON% src\cowork_estimator.py render >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 ( echo [%TIMESTAMP%] ERROR: render failed >> "%LOG%" & exit /b %ERRORLEVEL% )

echo [%TIMESTAMP%] BurnRate ingest completed successfully >> "%LOG%"

:: Keep last 500 lines of log
powershell -Command "Get-Content '%LOG%' -Tail 500 | Set-Content '%LOG%.tmp'; Move-Item -Force '%LOG%.tmp' '%LOG%'"

endlocal
