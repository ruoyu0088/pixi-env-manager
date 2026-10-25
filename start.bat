@echo off
setlocal
cd /d "%~dp0"
set "PYTHONW="

if defined PIXI_ENV_MANAGER_PYTHON (
    "%PIXI_ENV_MANAGER_PYTHON%" -c "import tkinter" >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] PIXI_ENV_MANAGER_PYTHON cannot import tkinter:
        echo %PIXI_ENV_MANAGER_PYTHON%
        pause
        exit /b 1
    )
    set "PYTHONW=%PIXI_ENV_MANAGER_PYTHON%"
    goto :run
)

rem This machine's standard Pixi workspace comes first.
if exist "C:\pixi_env\.pixi\envs\default\pythonw.exe" (
    set "PYTHONW=C:\pixi_env\.pixi\envs\default\pythonw.exe"
    goto :run
)

rem Per-user and machine-wide standard Python installations.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~fD\pythonw.exe" (
        "%%~fD\pythonw.exe" -c "import tkinter" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHONW=%%~fD\pythonw.exe"
            goto :run
        )
    )
)
for /d %%D in ("C:\Python3*") do (
    if exist "%%~fD\pythonw.exe" (
        "%%~fD\pythonw.exe" -c "import tkinter" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHONW=%%~fD\pythonw.exe"
            goto :run
        )
    )
)

rem Any pythonw.exe on PATH (verified without opening a console window).
for /f "delims=" %%I in ('where pythonw 2^>nul') do (
    "%%I" -c "import tkinter" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHONW=%%I"
        goto :run
    )
)

echo [ERROR] No working Python 3 with Tkinter was found.
echo Install Python 3.9+ from python.org (include Tcl/Tk),
echo or set PIXI_ENV_MANAGER_PYTHON to a pythonw.exe path.
pause
exit /b 1

:run
set "NEEDS_CONSOLE="
set "PASSWORD_MODE="
for %%A in (%*) do (
    if /I "%%~A"=="--web" set "NEEDS_CONSOLE=1"
    if /I "%%~A"=="--set-password" set "NEEDS_CONSOLE=1"
    if /I "%%~A"=="--set-password" set "PASSWORD_MODE=1"
    if /I "%%~A"=="--help" set "NEEDS_CONSOLE=1"
    if /I "%%~A"=="-h" set "NEEDS_CONSOLE=1"
)
set "RUNNER=%PYTHONW%"
if defined NEEDS_CONSOLE set "RUNNER=%PYTHONW:pythonw.exe=python.exe%"
if defined NEEDS_CONSOLE goto :run_console

start "" "%PYTHONW%" "%~dp0pixi_env_manager.py" %*
exit /b 0

:run_console
rem Web and password setup stay in this console, so errors and logs are visible.
"%RUNNER%" "%~dp0pixi_env_manager.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Pixi Environment Manager exited with code %RC%.
    echo If this is the Web UI, configure the password first:
    echo     start.bat --web --set-password
    pause
    exit /b %RC%
)
if defined PASSWORD_MODE pause
exit /b %RC%
