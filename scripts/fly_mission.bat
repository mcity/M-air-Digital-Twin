@echo off
rem Fly a mission file, for example: scripts\fly_mission.bat missions\mcity_circle.json
call "%~dp0_mair.bat" mission %*
exit /b %ERRORLEVEL%
