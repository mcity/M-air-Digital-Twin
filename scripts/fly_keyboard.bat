@echo off
rem Fly on the keyboard. The simulator must be running.
call "%~dp0_mair.bat" keyboard %*
exit /b %ERRORLEVEL%
