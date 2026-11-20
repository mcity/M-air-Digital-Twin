@echo off
rem Run your own Python script against the simulator: scripts\run_python.bat my_script.py
call "%~dp0_mair.bat" run %*
exit /b %ERRORLEVEL%
