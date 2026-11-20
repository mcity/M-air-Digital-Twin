@echo off
rem Start the simulator on the corridor level. Leave it running and fly from a second window.
call "%~dp0_mair.bat" sim %*
exit /b %ERRORLEVEL%
