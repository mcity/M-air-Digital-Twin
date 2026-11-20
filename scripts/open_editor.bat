@echo off
rem Open the project in the Unreal Editor (press Play there to start the simulator).
call "%~dp0_mair.bat" editor %*
exit /b %ERRORLEVEL%
