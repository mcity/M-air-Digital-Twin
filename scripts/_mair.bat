@echo off
rem Shared by the .bat files here: runs mair.py with the Python environment install.py made.
setlocal
set "MAIR_LAUNCHER=%~dp0..\.venv\Scripts\python.exe"
if not exist "%MAIR_LAUNCHER%" set "MAIR_LAUNCHER=python"
"%MAIR_LAUNCHER%" "%~dp0mair.py" %*
exit /b %ERRORLEVEL%
