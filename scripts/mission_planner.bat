@echo off
rem Draw a mission on a map (the flight planner of the plugin).
call "%~dp0_mair.bat" planner %*
exit /b %ERRORLEVEL%
