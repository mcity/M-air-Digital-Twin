@echo off
rem A one-minute check that everything works. The simulator must be running.
call "%~dp0_mair.bat" hover %*
exit /b %ERRORLEVEL%
